$SecurePassword = ConvertTo-SecureString -String "" -AsPlainText -Force
$TenantId = "<NPE SP Tenant ID>"
$ApplicationId = "<NPE SP App ID>"
$Credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $ApplicationId, $SecurePassword
Connect-AzAccount -ServicePrincipal -TenantId $TenantId -Credential $Credential -WarningAction Ignore

# Get all subscriptions list
$subscriptions = Get-AzSubscription
Write-Host "Total subscriptions: $($subscriptions.count)" -ForegroundColor Cyan

# Create output report file
$currentdate = Get-Date -Format "yyyy-MM-dd"
$filename= "CIS_Benchmark_Windows2022_Baseline_1_0_$currentdate"
$csvfilepath = ".\sourcefiles\$filename.csv"
$jsonfilepath = ".\sourcefiles\$filename.json"

if (Test-Path $csvfilepath) { 
    Remove-Item -Path $csvfilepath -Force 
    Remove-Item -Path $jsonfilepath -Force
}

$content= "bunit,subscription,report_id,date,host_name,region,environment,platform,status,id,title"
Add-Content -Path $csvfilepath -Value $content

$VMquery = "guestconfigurationresources
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project subscriptionId, id, name, location, resources = properties.latestAssignmentReport.resources, vmid = split(properties.targetResourceId, '/')[(-1)],
reportid = split(properties.latestReportId, '/')[(-1)], reporttime = properties.lastComplianceStatusChecked
| order by id"


$VMresults = Search-AzGraph -Query $VMquery

Write-Host "Total VMs across all subscriptions in NPE: $($VMresults.count)" -ForegroundColor Cyan

# Loop through each subscription
foreach ($sub in $subscriptions) {
    # Retrieve distinct VMs from Windows2022 compliance report
    $VMquery = @"guestconfigurationresources
| where subscriptionId == '$($sub.Id)'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project subscriptionId, id, name, location, resources = properties.latestAssignmentReport.resources, vmid = split(properties.targetResourceId, '/')[(-1)],
reportid = split(properties.latestReportId, '/')[(-1)], reporttime = properties.lastComplianceStatusChecked
| order by id 
"@

    $VMresults = Search-AzGraph -Query $VMquery
    if ($VMresults.count -gt 0) {
        Write-Host "Querying subscription Name: $($sub.Name), ID: $($sub.Id)" -ForegroundColor Cyan
        Write-Host "Total VMs in subscription $($sub.Name): $($VMresults.count)" -ForegroundColor Cyan
    }

    # Loop through each VM and fetch its compliance report
    foreach ($vm in $VMresults) {
        Write-Host "Querying VM: $($vm.vmid)" -ForegroundColor Cyan
        $compliancequery = @"
guestconfigurationresources
| where id == '$($vm.id)'
| where type =~ "microsoft.guestconfiguration/guestconfigurationassignments"
| where name contains 'CIS_Benchmark_Windows2022_Baseline_1_0'
| project subscriptionId, id, name, location, resources = properties.latestAssignmentReport.resources, vmid = split(properties.targetResourceId, '/')[(-1)],
reportid = split(properties.latestReportId, '/')[(-1)], reporttime = properties.lastComplianceStatusChecked
| order by id
| extend resources = iff(isnull(resources[0]), dynamic([{}]), resources)
| mv-expand resources limit 1000
| extend reasons = resources.reasons
| extend reasons = iff(isnull(reasons[0]), dynamic([{}]), reasons)
| mv-expand reasons
| project bunit="azure", subscription=subscriptionId, report_id=reportid, Date=format_datetime(todatetime(reporttime), "yyyy-MM-dd"), host_name=vmid,
region=location, environment=case(tolower(substring(vmid,5,1))=="d", "dev", tolower(substring(vmid,5,1))=="q", "qa", tolower(substring(vmid,5,1))=="u", "uat",tolower(substring(vmid,5,1))=='p',"prod", 'UNKNOWN'),platform=split(name,"_")[2], status = iif(reasons.phrase contains "This control is in the waiver list", "skipped", iif(resources.complianceStatus=="true","passed","failed")),id=split(resources.resourceID,'_'[3]),title = replace_string(tostring(resources.resourceId),"[WindowsControlTranslation]","")
"@
        $batchsize = 1000
        $complianceresult = Search-AzGraph -Query $compliancequery -First $batchsize
        Write-Host "Total row count: $($complianceresult.count)" -ForegroundColor Cyan

        foreach ($ctl in $complianceresult) {
            $resultline = "$($ctl.bunit),$($ctl.subscription),$($ctl.report_id),$($ctl.Date),$($ctl.host_name),$($ctl.region),$($ctl.environment),$($ctl.platform),$($ctl.status),$($ctl.id),$($ctl.title)"
            Add-Content -Path $csvfilepath -Value $resultline
        }
    }
}

Write-Host "All subscriptions processed"
Write-Host "Convert CSV to JSON"
Import-Csv -Path "$csvfilepath" | ConvertTo-Json -Depth 10 | Set-Content -Path "$jsonfilepath" -Encoding utf8
