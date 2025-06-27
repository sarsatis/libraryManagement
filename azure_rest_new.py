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

TENANT_ID = tenant_id
CLIENT_ID = client_id
CLIENT_SECRET = client_secret

PROXIES = {
    'http': 'http://statestr.com:80',
    'https': 'http://statestr.com:80',
}

BASELINES = [
    "CIS_Benchmark_Windows2022_Baseline_1_0",
    "CIS_Benchmark_Linux2022_Baseline_1_0",  # Example Linux baseline, add more if needed
]

# --------- Path Configuration ---------
SOURCE_FOLDER_NAME = "sourcefiles"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(CURRENT_DIR, SOURCE_FOLDER_NAME)

# --------- Queries ---------
WINDOWS_QUERY = """
guestconfigurationresources
| where subscriptionId == '{subscription_id}'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains '{baseline}'
| project 
    subscriptionId, 
    id, 
    name, 
    location, 
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
    subscriptionId, 
    id, 
    name, 
    location, 
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

def get_access_token(tenant_id, client_id, client_secret):
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://management.azure.com/.default"]
    app = msal.ConfidentialClientApplication(
        client_id, authority=authority, client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Failed to get token: {result.get('error_description')}")


def with_retries(request_func, max_retries=5, base_delay=2, retry_on=(429, 500, 502, 503, 504)):
    for attempt in range(1, max_retries + 1):
        try:
            response = request_func()
            if response.status_code in retry_on:
                retry_after = int(response.headers.get("Retry-After", base_delay))
                log(f"Retryable error ({response.status_code}). Retrying in {retry_after} seconds...", YELLOW)
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            log(f"Attempt {attempt}: {e}", RED)
            if attempt == max_retries:
                raise
            delay = base_delay * attempt
            log(f"Retrying in {delay} seconds...", YELLOW)
            time.sleep(delay)



def get_subscriptions(token):
    url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
    headers = {"Authorization": f"Bearer {token}"}
    response = with_retries(lambda: requests.get(url, headers=headers, proxies=PROXIES, verify=VERIFY_SSL))
    subs = response.json().get("value", [])
    return [(sub["subscriptionId"], sub["displayName"]) for sub in subs]


def run_resource_graph_query(token, subscription_id, baseline):
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if "linux" in baseline.lower():
        query = LINUX_QUERY.format(subscription_id=subscription_id, baseline=baseline)
    else:
        query = WINDOWS_QUERY.format(subscription_id=subscription_id, baseline=baseline)

    all_results = []
    page = 1
    skip_token = None

    while True:
        body = {
            "subscriptions": [subscription_id],
            "query": query,
            "options": {"resultFormat": "objectArray"}
        }
        if skip_token:
            body["options"]["$skipToken"] = skip_token

        # Use retry logic here
        response = with_retries(lambda: requests.post(url, headers=headers, json=body, proxies=PROXIES, verify=VERIFY_SSL))

        result_json = response.json()
        data = result_json.get("data", [])
        all_results.extend(data)

        if len(data) > 0:
            log(f"Page {page}: Fetched {len(data)} records (Total so far: {len(all_results)})", GRAY)

        skip_token = result_json.get("$skipToken")
        if not skip_token:
            break
        page += 1

    return all_results


def filter_message(message):
    # Patterns to remove (literal sequences of +, -, = signs of length >= 1)
    patterns = [
        r"\++",    # one or more plus signs
        r"\-+",    # one or more minus signs
        r"\=+"     # one or more equal signs
    ]

    combined_pattern = "(" + "|".join(patterns) + ")"
    cleaned_message = re.sub(combined_pattern, "", message)
    cleaned_message = cleaned_message.strip()

    return cleaned_message

# --------- Main ---------
def main():
    start_time = datetime.now()
    log(f"Start Time: {start_time}", GREEN)

    log("Authenticating and acquiring token...", GREEN)
    token = get_access_token(TENANT_ID, CLIENT_ID, CLIENT_SECRET)

    log("Retrieving Azure subscriptions...", GREEN)
    subscriptions = get_subscriptions(token)
    log(f"Total subscriptions: {len(subscriptions)}", YELLOW)

    current_date = start_time.strftime('%Y-%m-%d')
    os.makedirs(SOURCE_DIR, exist_ok=True)

    env_label = "UNKNOWN"
    NPE_CLIENT_IDS = {
        # Add your known NPE client IDs here
    }
    PROD_CLIENT_IDS = {
        # Add your known PROD client IDs here
    }

    if CLIENT_ID in NPE_CLIENT_IDS:
        env_label = "NPE"
    elif CLIENT_ID in PROD_CLIENT_IDS:
        env_label = "PROD"
    else:
        if "prod" in CLIENT_ID.lower():
            env_label = "PROD"
        else:
            env_label = "NPE"

    for baseline in BASELINES:
        log(f"\n--- Processing Baseline: {baseline} ---", BLUE)
        filename = f"{baseline}_REST_{env_label}_{current_date}"
        csv_filepath = os.path.join(SOURCE_DIR, f"{filename}.csv")
        json_filepath = os.path.join(SOURCE_DIR, f"{filename}.json")

        headers = ["bunit", "subscription", "report_id", "Date", "host_name", "region",
                   "environment", "platform", "status", "cis_id", "id", "message"]

        all_rows = []
        unique_vm_set = set()
        vm_control_info = defaultdict(lambda: defaultdict(list))

        log(f"Starting to collect data for baseline [{baseline}] across {len(subscriptions)} subscriptions...", CYAN)

        for sub_id, sub_name in subscriptions:
            results = run_resource_graph_query(token, sub_id, baseline)

            for r in results:
                r["message"] = filter_message(r.get("message", ""))
                if r["message"] == "":
                    continue

                unique_vm_set.add(r["host_name"])
                vm_control_info[sub_name][r["host_name"]].append(r)
                all_rows.append(r)

        log(f"\nTotal unique VMs for baseline [{baseline}]: {len(unique_vm_set)}", CYAN)
        log(f"Total rows for baseline [{baseline}]: {len(all_rows)}", CYAN)

        if not all_rows:
            log(f"No compliance data found for baseline: {baseline}", RED)
            continue

        # Updated printing format with colors
        for sub_name, vms in vm_control_info.items():
            log(f"{baseline} - {sub_name}", MAGENTA)
            for vm, controls in vms.items():
                log(f"    ({vm}) : {len(controls)} controls", CYAN)
        
                cis_id_counts = defaultdict(int)
                for control in controls:
                    cis_id = control.get("cis_id")
                    if cis_id:
                        cis_id_counts[cis_id] += 1
        
                duplicates = [cid for cid, count in cis_id_counts.items() if count > 1]
        
                if duplicates:
                    total_duplicate_vm_count += 1
                    log(f"        {len(duplicates)} duplicated cis_id(s) found!", YELLOW)
                    for d in duplicates:
                        log(f"            - Duplicated cis_id: {d} (count: {cis_id_counts[d]})", RED)

        log(f"\nWriting CSV to: {csv_filepath}", GREEN)
        with open(csv_filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in all_rows:
                filtered_row = {key: row.get(key, "") for key in headers}
                writer.writerow(filtered_row)

        log(f"Writing JSON to: {json_filepath}", GREEN)
        with open(json_filepath, mode="w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)

        log(f"\nDone writing for baseline: {baseline}", GREEN)

    end_time = datetime.now()
    duration = end_time - start_time
    log(f"\nEnd Time: {end_time}", GREEN)
    log(f"Total Execution Time: {duration}", GREEN)

if __name__ == "__main__":
    main()
