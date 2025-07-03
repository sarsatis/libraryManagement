import requests
import msal
import json
import csv
import os
from datetime import datetime
import urllib3
from collections import defaultdict
import re
import time
import sys

# --------- Disable SSL warnings ---------
VERIFY_SSL = False
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------- ANSI Color Codes ---------
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
GRAY = "\033[90m"
RESET = "\033[0m"

# --------- Logger ---------
def supports_color():
    return sys.stdout.isatty()

def log(msg, color=RESET):
    if supports_color():
        print(f"{color}{msg}{RESET}")
    else:
        print(msg)

# --------- Azure Auth ---------
tenant_id = os.getenv("tenant_id")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
exec_mode = "weekly_cis_azure"

TENANT_ID = tenant_id
CLIENT_ID = client_id
CLIENT_SECRET = client_secret

PROXIES = {
    'http': 'http://proxy.statestr.com:80',
    'https': 'http://proxy.statestr.com:80'
}

BASELINES = [
    "CIS_Benchmark_Windows2022_Baseline_1_0",
    # Add more as needed
]

# --------- Queries ---------
WINDOWS_QUERY = """
guestconfigurationresources
| where id == '{resource_id}'
| project subscriptionId, id, name, location,
    resources = properties.latestAssignmentReport.resources,
    vmid = split(properties.targetResourceId, "/")[-1],
    reportid = split(properties.latestReportId, "/")[-1],
    reporttime = properties.lastComplianceStatusChecked
| mv-expand resources
| extend reasons = resources.reasons
| mv-expand reasons
| extend raw_message = tostring(reasons.phrase)
| extend clean_message = trim(" ", replace_string(replace_string(raw_message, "\\n", " "), "\\r", " "))
| project
    bunit = "azure",
    subscription = subscriptionId,
    report_id = reportid,
    Date = format_datetime(todatetime(reporttime), "yyyy-MM-dd"),
    host_name = vmid,
    region = location,
    environment = case(
        tolower(host_name) has "dev", "dev",
        tolower(substring(host_name, 5, 1)) == "d", "dev",
        tolower(substring(host_name, 5, 1)) == "q", "qa",
        tolower(substring(host_name, 5, 1)) == "u", "uat",
        tolower(substring(host_name, 5, 1)) == "p", "prod",
        "UNKNOWN"),
    platform = split(name, "_")[2],
    status = iif(
        raw_message has "waiver list", "skipped",
        iif(resources.complianceStatus == "true", "passed", "failed")
    ),
    cis_id = split(resources.resourceId, "_")[3],
    id = replace_string(tostring(resources.resourceId), "[WindowsControlTranslation]", ""),
    message = clean_message
"""

LINUX_QUERY = """
guestconfigurationresources
| where id == '{resource_id}'
| project subscriptionId, id, name, location,
    resources = properties.latestAssignmentReport.resources,
    vmid = split(properties.targetResourceId, "/")[-1],
    reportid = split(properties.latestReportId, "/")[-1],
    reporttime = properties.lastComplianceStatusChecked
| mv-expand resources
| extend raw_message = iif(array_length(resources.reasons) > 0, tostring(resources.reasons[0].phrase), "")
| extend clean_message = trim(" ", replace_string(replace_string(raw_message, "\\n", " "), "\\r", " "))
| project
    bunit = "azure",
    subscription = subscriptionId,
    report_id = reportid,
    Date = format_datetime(todatetime(reporttime), "yyyy-MM-dd"),
    host_name = vmid,
    region = location,
    environment = case(
        tolower(host_name) has "dev", "dev",
        tolower(substring(host_name, 5, 1)) == "d", "dev",
        tolower(substring(host_name, 5, 1)) == "q", "qa",
        tolower(substring(host_name, 5, 1)) == "u", "uat",
        tolower(substring(host_name, 5, 1)) == "p", "prod",
        "UNKNOWN"),
    platform = split(name, "_")[2],
    status = iif(
        clean_message has "waiver list", "skipped",
        iif(resources.complianceStatus == "true", "passed", "failed")
    ),
    cis_id = split(resources.resourceId, "_")[3],
    id = replace_string(tostring(resources.resourceId), "[LinuxControlTranslation]", ""),
    message = clean_message
"""

VM_LIST_QUERY = """
guestconfigurationresources
| where subscriptionId == '{subscription_id}'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains '{baseline}'
| project id, vmid = split(properties.targetResourceId, '/')[(-1)]
| order by id
"""

def get_source_directory(bunit):
    source_folder = f"{bunit}_sourcefiles"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), source_folder)

def get_access_token(tenant_id, client_id, client_secret):
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret
    )
    result = app.acquire_token_for_client(scopes=["https://management.azure.com/.default"])
    if "access_token" in result:
        return result["access_token"]
    raise Exception(f"Auth failed: {result.get('error_description')}")

def with_retries(request_func, max_retries=5, base_delay=2, retry_on=(429,500,502,503,504)):
    for i in range(1, max_retries+1):
        try:
            r = request_func()
            if r.status_code in retry_on:
                delay = int(r.headers.get("Retry-After", base_delay))
                log(f"Retryable error {r.status_code}, retrying in {delay}s...", YELLOW)
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            log(f"Attempt {i}: {e}", RED)
            if i == max_retries:
                raise
            time.sleep(base_delay*i)

def get_subscriptions(token):
    url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
    hdr = {"Authorization": f"Bearer {token}"}
    res = with_retries(lambda: requests.get(url, headers=hdr, proxies=PROXIES, verify=VERIFY_SSL))
    return [(s["subscriptionId"], s["displayName"]) for s in res.json().get("value", [])]

def run_resource_graph_query(token, subscription_id, query):
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"
    body = {"subscriptions":[subscription_id], "query":query, "options":{"resultFormat":"objectArray"}}
    hdr = {"Authorization": f"Bearer {token}", "Content-Type":"application/json"}
    res = with_retries(lambda: requests.post(url, headers=hdr, json=body, proxies=PROXIES, verify=VERIFY_SSL))
    return res.json().get("data", [])

def filter_message(msg):
    pat = "(" + "|".join([r"\++", r"\-+", r"\=+"]) + ")"
    return re.sub(pat, "", msg or "").strip()

def main(bunit):
    start = datetime.now()
    log(f"Start Time: {start}", GREEN)
    token = get_access_token(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    log("Authenticating done.", GREEN)

    subs = get_subscriptions(token)
    log(f"Total subscriptions: {len(subs)}", YELLOW)

    date_str = start.strftime("%Y-%m-%d")
    src = get_source_directory(bunit)
    os.makedirs(src, exist_ok=True)
    env_label = "PROD" if "prod" in CLIENT_ID.lower() else "NPE"

    for baseline in BASELINES:
        log(f"\n--- Processing Baseline: {baseline} ---", BLUE)
        fname = f"{baseline}_REST_{env_label}_{date_str}"
        csv_fp = os.path.join(src, f"{fname}.csv")
        json_fp = os.path.join(src, f"{fname}.json")

        cols = ["bunit","subscription","report_id","date","host_name","region",
                "environment","platform","status","cis_id","id","message","exec_mode"]
        all_rows = []
        uid = set()
        info = defaultdict(lambda: defaultdict(list))

        for sub_id, sub_name in subs:
            vm_q = VM_LIST_QUERY.format(subscription_id=sub_id, baseline=baseline)
            vms = run_resource_graph_query(token, sub_id, vm_q)
            for vm in vms:
                rid = vm["id"]
                if "windows" in baseline.lower():
                    cq = WINDOWS_QUERY.format(resource_id=rid)
                else:
                    cq = LINUX_QUERY.format(resource_id=rid)
                data = run_resource_graph_query(token, sub_id, cq)
                for r in data:
                    r["message"] = filter_message(r.get("message"))
                    r["exec_mode"] = exec_mode
                    uid.add(r["host_name"])
                    info[sub_name][r["host_name"]].append(r)
                    all_rows.append(r)

        log(f"Total unique VMs for {baseline}: {len(uid)}", CYAN)
        log(f"Total rows: {len(all_rows)}", CYAN)
        if not all_rows:
            log(f"No data found for {baseline}", RED)
            continue

        dup_count = 0
        for sub_name, vms in info.items():
            log(f"{baseline} - {sub_name}", MAGENTA)
            for vm, ctrls in vms.items():
                log(f"    ({vm}): {len(ctrls)} controls", CYAN)
                counts = defaultdict(int)
                for c in ctrls:
                    cid = c.get("cis_id")
                    if cid:
                        counts[cid] += 1
                dups = [cid for cid, cnt in counts.items() if cnt > 1]
                if dups:
                    dup_count += 1
                    log(f"        {len(dups)} duplicated CIS IDs", YELLOW)
                    for d in dups:
                        log(f"            - {d} (count {counts[d]})", RED)

        log(f"\nWriting CSV to: {csv_fp}", GREEN)
        with open(csv_fp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in all_rows:
                w.writerow({k: row.get(k, "") for k in cols})

        log(f"Writing JSON to: {json_fp}", GREEN)
        with open(json_fp, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)

        log(f"\nDone: {baseline}, duplicates VMs: {dup_count}", GREEN)

    end = datetime.now()
    log(f"\nEnd Time: {end}", GREEN)
    log(f"Total Duration: {end - start}", GREEN)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python azuregraph_rest.py <business_unit>")
        sys.exit(1)
    main(sys.argv[1])
