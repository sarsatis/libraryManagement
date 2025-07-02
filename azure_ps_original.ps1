$SecurePassword = ConvertTo-SecureString -String "" -AsPlainText -Force
$TenantId = "<NPE SP Tenant ID>"
$ApplicationId = "<NPE SP App ID>"
$Credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $ApplicationId, $SecurePassword
Connect-AzAccount -ServicePrincipal -TenantId $TenantId -Credential $Credential -WarningAction Ignore

$startTime = Get-Date
Write-Host "Start Time: $startTime" -ForegroundColor Yellow

# Get all subscriptions list
$subscriptions = Get-AzSubscription
Write-Host "Total subscriptions: $($subscriptions.count)" -ForegroundColor Cyan

# Create output report file
$exec_mode  = "weekly_cis_azure"
$currentdate = Get-Date -Format "yyyy-MM-dd"
$environment = "NPE"
$filename= "CIS_Benchmark_Windows2022_Baseline_1_0_OPTIMISED_$($environment)_$currentdate"
$sourcepath = ".\sourcefiles"
$csvfilepath = "$sourcepath\$filename.csv"
$jsonfilepath = "$sourcepath\$filename.json"

if (Test-Path $csvfilepath) { 
    Remove-Item -Path $csvfilepath -Force 
    Remove-Item -Path $jsonfilepath -Force
}
if (-not (test-Path -Path $sourcepath)) {
    New-Item -ItemType Directory -Path "$sourcepath"
}

$allCsvLines = @()
$csvHeader= "bunit,subscription,report_id,date,host_name,region,environment,platform,status,cis_id,id,exec_mode"
$allCsvLines += $csvHeader


$VMquery = @"
guestconfigurationresources
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project id
| order by id
"@


$VMresults = Search-AzGraph -Query $VMquery -First 1000

Write-Host "Total VMs in all subscriptions $($VMresults.count)" -ForegroundColor Yellow

# Loop through each subscription
foreach ($sub in $subscriptions) {
    # Retrieve distinct VMs from Windows2022 compliance report
    $VMquery = @"
guestconfigurationresources
| where subscriptionId == '$($sub.Id)'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project id, vmid = split(properties.targetResourceId, '/')[(-1)]
| order by id 
"@

    $VMresults = Search-AzGraph -Query $VMquery -First 1000
    if ($VMresults.count -gt 0) {
        Write-Host "Querying subscription Name: $($sub.Name), ID: $($sub.Id)" -ForegroundColor Yellow
        Write-Host "Total VMs in subscription $($sub.Name): $($VMresults.count)" -ForegroundColor Yellow
    } else {
        continue
    }

    # Loop through each VM and fetch its compliance report
    foreach ($vm in $VMresults) {
        Write-Host "Querying VM: $($vm.vmid)" -ForegroundColor Cyan
        
        $compliancequery = @"
guestconfigurationresources
| where id == '$($vm.id)'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project subscriptionId, id, name, location, resources = properties.latestAssignmentReport.resources, vmid = split(properties.targetResourceId, '/')[(-1)],
reportid = split(properties.latestReportId, '/')[(-1)], reporttime = properties.lastComplianceStatusChecked
| order by id
| extend resources = iff(isnull(resources[0]), dynamic([{}]), resources)
| mv-expand resources limit 1000
| extend reasons = resources.reasons
| extend reasons = iff(isnull(reasons[0]), dynamic([{}]), reasons)
| mv-expand reasons
| project 
    bunit="azure", 
    subscription=subscriptionId, 
    report_id=reportid, 
    Date=format_datetime(todatetime(reporttime), "yyyy-MM-dd"), 
    host_name=vmid,
    region=location, 
    environment=case(
        tolower(vmid) contains_cs 'dev', 'dev',
        tolower(substring(vmid,5,1))=="d", "dev", 
        tolower(substring(vmid,5,1))=="q", "qa", 
        tolower(substring(vmid,5,1))=="u", "uat",
        tolower(substring(vmid,5,1))=="p","prod", 
        "UNKNOWN"
    ),
    platform=split(name,"_")[2], 
    status = iif(
        reasons.phrase contains "This control is in the waiver list", 
        "skipped", 
        iif(resources.complianceStatus=="true","passed","failed")
    ),
    cis_id = split(resources.resourceId,"_")[3],
    id = replace_string(tostring(resources.resourceId), "[WindowsControlTranslation]", "")
"@
        $batchsize = 1000
        $skip = 0
        $complianceResults = @()

        do {
            if ($skip -eq 0) {
                $pagedResults = Search-AzGraph -Query $compliancequery -First $batchsize
            } else {
                $pagedResults = Search-AzGraph -Query $compliancequery -First $batchsize -Skip $skip
            }

            $complianceResults += $pagedResults
            $skip += $batchsize
        } while ($pagedResults.Count -eq $batchsize)

        Write-Host "Total row count for VM $($vm.vmid): $($complianceResults.Count)" -ForegroundColor Cyan

        foreach ($ctl in $complianceResults) {
            $resultline = "$($ctl.bunit),$($ctl.subscription),$($ctl.report_id),$($ctl.Date),$($ctl.host_name),$($ctl.region),$($ctl.environment),$($ctl.platform),$($ctl.status),$($ctl.cis_id),$($ctl.id),$($exec_mode)"
            $allCsvLines += $resultline
        }
    }
}


Write-Host "Writing all results to CSV file..." -ForegroundColor Yellow
$allCsvLines | Set-Content -Path $csvfilepath -Encoding UTF8

Write-Host "Converting CSV to JSON..." -ForegroundColor Yellow
Import-Csv -Path $csvfilepath | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonfilepath -Encoding UTF8


$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host "End Time: $endTime" -ForegroundColor Yellow
Write-Host "Total Execution Time: $($duration.ToString())" -ForegroundColor Green
