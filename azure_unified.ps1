# -------------------- Secure Login --------------------
$SecurePassword = ConvertTo-SecureString -String "" -AsPlainText -Force
$TenantId = "<NPE SP Tenant ID>"
$ApplicationId = "<NPE SP App ID>"
$Credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $ApplicationId, $SecurePassword
Connect-AzAccount -ServicePrincipal -TenantId $TenantId -Credential $Credential -WarningAction Ignore

# -------------------- Start Timer --------------------
$startTime = Get-Date
Write-Host "Start Time: $startTime" -ForegroundColor Yellow

# -------------------- File Setup --------------------
$subscriptions = Get-AzSubscription
$totalSubscriptions = $subscriptions.Count
Write-Host "Total subscriptions: $totalSubscriptions" -ForegroundColor Cyan

$currentDate = Get-Date -Format "yyyy-MM-dd"
$basePath = ".\sourcefiles"

# -------------------- Baselines --------------------
$baselines = @(
    "CIS_Benchmark_Windows2022_Baseline_1_0",
    "CIS_Benchmark_Windows2019_Baseline_1_0"
)

# -------------------- Process Each Baseline --------------------
foreach ($baseline in $baselines) {
    $csvFilePath = "$basePath\$baseline`_$currentDate.csv"
    $jsonFilePath = "$basePath\$baseline`_$currentDate.json"

    Remove-Item -Path $csvFilePath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $jsonFilePath -Force -ErrorAction SilentlyContinue

    $allCsvLines = @()
    $csvHeader = "bunit,subscription,report_id,Date,host_name,region,environment,platform,status,cis_id,id,message"
    $allCsvLines += $csvHeader

    $baselineTotalVms = 0
    $baselineTotalRows = 0

    # -------------------- Subscription Loop --------------------
    foreach ($sub in $subscriptions) {
        $subId = $sub.Id
        $subName = $sub.Name

        $complianceQuery = @"
guestconfigurationresources
| where subscriptionId == '$subId'
| where type =~ 'microsoft.guestconfiguration/guestconfigurationassignments'
| where name contains '$baseline'
| project 
    subscriptionId, 
    id, 
    name, 
    location, 
    resources = properties.latestAssignmentReport.resources, 
    vmid = split(properties.targetResourceId, '/')[(-1)],
    reportid = split(properties.latestReportId, '/')[(-1)], 
    reporttime = properties.lastComplianceStatusChecked
| extend resources = iff(isnull(resources[0]), dynamic([{}]), resources)
| mv-expand resources limit 1000
| extend reasons = resources.reasons
| extend reasons = iff(isnull(reasons[0]), dynamic([{}]), reasons)
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
    cis_id = split(resources.resourceID, "_")[3], 
    id = replace_string(tostring(resources.resourceId), "[WindowsControlTranslation]", ""),
    message = reasons.phrase
"@

        # Pagination
        $batchSize = 1000
        $skip = 0
        $allResults = @()

        do {
            if ($skip -eq 0) {
                $pagedResults = Search-AzGraph -Query $complianceQuery -First $batchSize
            } else {
                $pagedResults = Search-AzGraph -Query $complianceQuery -First $batchSize -Skip $skip
            }

            $allResults += $pagedResults
            $skip += $batchSize
        } while ($pagedResults.Count -eq $batchSize)

        if ($allResults.Count -gt 0) {
            $rowCount = $allResults.Count
            $uniqueVmCount = ($allResults | Select-Object -ExpandProperty host_name -Unique).Count

            Write-Host "[$baseline] - $subName ($subId): $uniqueVmCount unique VMs, $rowCount rows" -ForegroundColor Cyan

            $baselineTotalVms += $uniqueVmCount
            $baselineTotalRows += $rowCount

            foreach ($r in $allResults) {
                $cleanMessage = $r.message -replace '\r?\n', ' ' -replace '"', '""'
                $line = "$($r.bunit),$($r.subscription),$($r.report_id),$($r.Date),$($r.host_name),$($r.region),$($r.environment),$($r.platform),$($r.status),$($r.cis_id),$($r.id),$cleanMessage"
                $allCsvLines += $line
            }
        }
    }

    # Export CSV
    Write-Host "Writing results to CSV: $csvFilePath" -ForegroundColor Yellow
    $allCsvLines | Set-Content -Path $csvFilePath -Encoding UTF8

    # Export JSON
    Write-Host "Exporting to JSON: $jsonFilePath" -ForegroundColor Yellow
    Import-Csv -Path $csvFilePath | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonFilePath -Encoding UTF8

    # Print baseline summary
    Write-Host "Total unique VMs for baseline [$baseline]: $baselineTotalVms" -ForegroundColor Green
    Write-Host "Total rows for baseline [$baseline]: $baselineTotalRows" -ForegroundColor Green
}

# -------------------- End Timer --------------------
$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host "End Time: $endTime" -ForegroundColor Yellow
Write-Host "Total Execution Time: $($duration.ToString())" -ForegroundColor Green
