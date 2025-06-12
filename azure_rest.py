import requests
import msal
import json
import csv
import os
from datetime import datetime
import urllib3
from collections import defaultdict
import re

# --------- Disable SSL warnings if verification is disabled ---------
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

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

# --------- Azure Auth ---------
tenant_id = os.getenv("tenant_id")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")

TENANT_ID = tenant_id
CLIENT_ID = client_id
CLIENT_SECRET = client_secret

PROXIES = {
    'http': 'http://proxy.statestr.com:80',
    'https': 'http://proxy.statestr.com:80',
}

# --------- Baselines and Client ID Mapping ---------
WINDOWS_BASELINES = ["CIS_Benchmark_Windows2022_Baseline_1_0"]
LINUX_BASELINES = ["CIS_Benchmark_UbuntuLinux1604_Baseline_1_0"]

ENV_CLIENT_MAP = {
    "npe-client-id-uuid-string": "NPE",
    "prod-client-id-uuid-string": "PROD"
}

BASELINES = WINDOWS_BASELINES + LINUX_BASELINES

# --------- KQL Templates ---------
WINDOWS_QUERY = """
guestconfigurationresources
| where subscriptionId == '{subscription_id}'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains '{baseline}'
| project 
    subscriptionId, id, name, location, 
    resources = properties.latestAssignmentReport.resources, 
    vmid = split(properties.targetResourceId, '/')[(-1)],
    reportid = split(properties.latestReportId, '/')[(-1)], 
    reporttime = properties.lastComplianceStatusChecked
| extend resources = iff(isnull(resources[0]), dynamic([{{}}]), resources)
| mv-expand resources limit 1000
| extend reasons = resources.reasons
| extend reasons = iff(isnull(reasons[0]), dynamic([{{}}]), reasons)
| mv-expand reasons
| extend raw_message = tostring(reasons.phrase)
| extend clean_message = trim(" ", replace_string(replace_string(raw_message, "\\n", " "), "\\r", " "))
| order by id
| project 
    bunit = "azure", 
    subscription = subscriptionId, 
    report_id = reportid, 
    Date = format_datetime(todatetime(reporttime), "yyyy-MM-dd"), 
    host_name = vmid,
    region = location, 
    environment = case(
        tolower(substring(vmid, 5, 1)) == "d", "dev",
        tolower(substring(vmid, 5, 1)) == "q", "qa",
        tolower(substring(vmid, 5, 1)) == "u", "uat",
        tolower(substring(vmid, 5, 1)) == "p", "prod",
        "UNKNOWN"
    ),
    platform = split(name, "_")[2], 
    status = iif(
        raw_message contains "This control is in the waiver list", 
        "skipped", 
        iif(resources.complianceStatus == "true", "passed", "failed")
    ),
    cis_id = split(resources.resourceId, "_")[3], 
    id = replace_string(tostring(resources.resourceId), "[WindowsControlTranslation]", ""),
    message = clean_message
"""

LINUX_QUERY = """
guestconfigurationresources
| where subscriptionId == '{subscription_id}'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains '{baseline}'
| project 
    subscriptionId, id, name, location, 
    resources = properties.latestAssignmentReport.resources, 
    vmid = split(properties.targetResourceId, '/')[(-1)],
    reportid = split(properties.latestReportId, '/')[(-1)], 
    reporttime = properties.lastComplianceStatusChecked
| extend resources = iff(isnull(resources[0]), dynamic([{{}}]), resources)
| mv-expand resources limit 1000
| extend reasons = resources.reasons
| extend reasons = iff(isnull(reasons[0]), dynamic([{{}}]), reasons)
| mv-expand reasons
| extend raw_message = tostring(reasons.phrase)
| extend clean_message = trim(" ", replace_string(replace_string(raw_message, "\\n", " "), "\\r", " "))
| order by id
| project 
    bunit = "azure", 
    subscription = subscriptionId, 
    report_id = reportid, 
    Date = format_datetime(todatetime(reporttime), "yyyy-MM-dd"), 
    host_name = vmid,
    region = location, 
    environment = case(
        tolower(substring(vmid, 5, 1)) == "d", "dev",
        tolower(substring(vmid, 5, 1)) == "q", "qa",
        tolower(substring(vmid, 5, 1)) == "u", "uat",
        tolower(substring(vmid, 5, 1)) == "p", "prod",
        "UNKNOWN"
    ),
    platform = split(name, "_")[2], 
    status = iif(
        raw_message contains "This control is in the waiver list", 
        "skipped", 
        iif(resources.complianceStatus == "true", "passed", "failed")
    ),
    cis_id = split(resources.resourceId, "_")[3], 
    id = replace_string(tostring(resources.resourceId), "[LinuxControlTranslation]", ""),
    message = clean_message
"""

def get_query_template(baseline):
    if baseline in WINDOWS_BASELINES:
        return WINDOWS_QUERY
    elif baseline in LINUX_BASELINES:
        return LINUX_QUERY
    else:
        raise ValueError(f"Unsupported baseline: {baseline}")

def clean_message_text(msg):
    return re.sub(r"[-=+]{4,}", "", msg).strip()

def get_env_from_client_id(client_id):
    return ENV_CLIENT_MAP.get(client_id, "UNKNOWN")

def get_access_token(tenant_id, client_id, client_secret):
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://management.azure.com/.default"]
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        return result["access_token"]
    raise Exception(f"Token error: {result.get('error_description')}")

def get_subscriptions(token):
    url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, proxies=PROXIES, verify=VERIFY_SSL)
    resp.raise_for_status()
    subs = resp.json().get("value", [])
    return [(sub["subscriptionId"], sub["displayName"]) for sub in subs]

def run_resource_graph_query(token, subscription_id, baseline):
    query = get_query_template(baseline).format(subscription_id=subscription_id, baseline=baseline)
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    all_results = []
    skip_token = None
    page = 1

    while True:
        body = {
            "subscriptions": [subscription_id],
            "query": query,
            "options": {"resultFormat": "objectArray"}
        }
        if skip_token:
            body["options"]["$skipToken"] = skip_token

        resp = requests.post(url, headers=headers, json=body, proxies=PROXIES, verify=VERIFY_SSL)
        resp.raise_for_status()
        result_json = resp.json()

        data = result_json.get("data", [])
        all_results.extend(data)

        if len(data) > 0:
            log(f"Page {page}: Fetched {len(data)} records (Total: {len(all_results)})", GRAY)

        skip_token = result_json.get("$skipToken")
        if not skip_token:
            break
        page += 1

    return all_results

def main():
    log("Authenticating and acquiring token...", GREEN)
    token = get_access_token(TENANT_ID, CLIENT_ID, CLIENT_SECRET)

    log("Fetching Azure subscriptions...", GREEN)
    subscriptions = get_subscriptions(token)
    log(f"Total subscriptions: {len(subscriptions)}", YELLOW)

    current_date = datetime.now().strftime('%Y-%m-%d')
    os.makedirs("sourcefiles", exist_ok=True)
    environment = get_env_from_client_id(CLIENT_ID)

    for baseline in BASELINES:
        log(f"\n--- Processing Baseline: {baseline} ---", BLUE)
        filename = f"{baseline}_REST_{environment}_{current_date}"
        csv_path = f"./sourcefiles/{filename}.csv"
        json_path = f"./sourcefiles/{filename}.json"

        headers = ["bunit", "subscription", "report_id", "Date", "host_name", "region",
                   "environment", "platform", "status", "cis_id", "id", "message"]

        all_rows = []
        vm_control_info = defaultdict(lambda: defaultdict(list))
        unique_vm_set = set()

        for sub_id, sub_name in subscriptions:
            results = run_resource_graph_query(token, sub_id, baseline)

            for r in results:
                r["message"] = clean_message_text(r.get("message", ""))
                all_rows.append(r)
                unique_vm_set.add(r["host_name"])
                vm_control_info[sub_name][r["host_name"]].append(r)

        log(f"\nTotal VMs: {len(unique_vm_set)} | Total Records: {len(all_rows)}", CYAN)

        if not all_rows:
            log(f"No data found for baseline: {baseline}", RED)
            continue

        for sub_name, vms in vm_control_info.items():
            for vm, controls in vms.items():
                log(f"{baseline} - {sub_name} ({vm}): {len(controls)} controls", MAGENTA)

        log(f"\nWriting CSV to: {csv_path}", GREEN)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in all_rows:
                writer.writerow({key: row.get(key, "") for key in headers})

        log(f"Writing JSON to: {json_path}", GREEN)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)

        log(f"\n✅ Done processing: {baseline}", GREEN)

if __name__ == "__main__":
    main()
