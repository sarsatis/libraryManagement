import requests
import msal
import json
import csv
import os
from datetime import datetime
import urllib3
from collections import defaultdict
from colorama import init, Fore, Style

# --------- Initialize Colorama ---------
init(autoreset=True)

# --------- Disable SSL warnings ---------
VERIFY_SSL = False
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------- Environment Variables ---------
tenant_id = os.getenv("tenant_id")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")

# --------- Configurations ---------
TENANT_ID = tenant_id
CLIENT_ID = client_id
CLIENT_SECRET = client_secret

PROXIES = {
    'http': 'http://statestr.com:80',
    'https': 'http://statestr.com:80',
}

# --------- List of Baselines ---------
BASELINES = [
    "CIS_Benchmark_Windows2022_Baseline_1_0",
    # Add more baselines here if needed
]

# --------- KQL Query Template ---------
QUERY_TEMPLATE = """
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
        reasons.phrase contains "This control is in the waiver list", 
        "skipped", 
        iif(resources.complianceStatus == "true", "passed", "failed")
    ),
    cis_id = split(resources.resourceId, "_")[3], 
    id = replace_string(tostring(resources.resourceId), "[WindowsControlTranslation]", ""),
    message = reasons.phrase
"""

# --------- Colored Logger ---------
def log(msg, color=Fore.WHITE):
    print(f"{color}{msg}{Style.RESET_ALL}")

# --------- Azure Token ---------
def get_access_token(tenant_id, client_id, client_secret):
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://management.azure.com/.default"]
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Failed to get token: {result.get('error_description')}")

# --------- Get Subscriptions ---------
def get_subscriptions(token):
    url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, proxies=PROXIES, verify=VERIFY_SSL)
    resp.raise_for_status()
    subs = resp.json().get("value", [])
    return [(sub["subscriptionId"], sub["displayName"]) for sub in subs]

# --------- Run Resource Graph Query ---------
def run_resource_graph_query(token, subscription_id, baseline):
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = QUERY_TEMPLATE.format(subscription_id=subscription_id, baseline=baseline)

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

        response = requests.post(url, headers=headers, json=body, proxies=PROXIES, verify=VERIFY_SSL)
        response.raise_for_status()
        result_json = response.json()

        data = result_json.get("data", [])
        all_results.extend(data)
        if data:
            log(f"  Page {page}: Fetched {len(data)} records (Total so far: {len(all_results)})", Fore.LIGHTBLACK_EX)

        skip_token = result_json.get("$skipToken")
        if not skip_token:
            break
        page += 1

    return all_results

# --------- Main Execution ---------
def main():
    log("Authenticating and acquiring token...", Fore.GREEN)
    token = get_access_token(TENANT_ID, CLIENT_ID, CLIENT_SECRET)

    log("Retrieving Azure subscriptions...", Fore.YELLOW)
    subscriptions = get_subscriptions(token)
    log(f"Total subscriptions: {len(subscriptions)}", Fore.YELLOW)

    start_time = datetime.now()
    log(f"Start Time: {start_time}", Fore.GREEN)

    current_date = start_time.strftime('%Y-%m-%d')
    os.makedirs("sourcefiles", exist_ok=True)

    for baseline in BASELINES:
        log(f"\n--- Processing Baseline: {baseline} ---", Fore.BLUE)

        filename = f"{baseline}_REST_{current_date}"
        csv_filepath = f"./sourcefiles/{filename}.csv"
        json_filepath = f"./sourcefiles/{filename}.json"

        headers = ["bunit", "subscription", "report_id", "Date", "host_name", "region",
                   "environment", "platform", "status", "cis_id", "id", "message"]

        all_rows = []
        unique_vm_set = set()

        for sub_id, sub_name in subscriptions:
            results = run_resource_graph_query(token, sub_id, baseline)

            vm_control_map = defaultdict(list)
            for r in results:
                vm_control_map[r["host_name"]].append(r)

            for vm, controls in vm_control_map.items():
                unique_vm_set.add(vm)
                log(f"{baseline} - {sub_name} ({sub_id}) ({vm}) : {len(controls)} controls", Fore.MAGENTA)
                all_rows.extend(controls)

        log(f"\nTotal unique VMs for baseline [{baseline}]: {len(unique_vm_set)}", Fore.CYAN)
        log(f"Total rows for baseline [{baseline}]: {len(all_rows)}", Fore.CYAN)

        if not all_rows:
            log(f"No compliance data found for baseline: {baseline}", Fore.RED)
            continue

        log(f"Writing CSV to: {csv_filepath}", Fore.LIGHTBLUE_EX)
        with open(csv_filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in all_rows:
                filtered_row = {key: row.get(key, "") for key in headers}
                writer.writerow(filtered_row)

        log(f"Writing JSON to: {json_filepath}", Fore.LIGHTBLUE_EX)
        with open(json_filepath, mode="w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)

        log(f"Done writing for baseline: {baseline}", Fore.GREEN)

    end_time = datetime.now()
    duration = end_time - start_time
    log(f"\nEnd Time: {end_time}", Fore.GREEN)
    log(f"Total Execution Time: {duration}", Fore.GREEN)

if __name__ == "__main__":
    main()
