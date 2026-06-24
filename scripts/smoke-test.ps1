param(
  [string]$FrontendBaseUrl = "http://127.0.0.1:3000",
  [string]$BackendBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
  param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Uri,
    [object]$Body = $null
  )

  $params = @{
    Method = $Method
    Uri = $Uri
  }

  if ($null -ne $Body) {
    $params.ContentType = "application/json; charset=utf-8"
    $params.Body = ($Body | ConvertTo-Json -Depth 12)
  }

  Invoke-RestMethod @params
}

function New-UnicodeText {
  param([int[]]$CodePoints)
  -join ($CodePoints | ForEach-Object { [char]$_ })
}

$TermKetoprofen = New-UnicodeText @(52992, 53664, 54532, 47196, 54172)
$CategoryInternal = New-UnicodeText @(45236, 44284)
$CategorySurgery = New-UnicodeText @(50808, 44284)
$DoseUnitTablet = New-UnicodeText @(51221)
$patientId = $null

try {
  $health = Invoke-Json -Method Get -Uri "$BackendBaseUrl/health"
  if ($health.status -ne "ok") {
    throw "Backend health check failed."
  }

  $dbHealth = Invoke-Json -Method Get -Uri "$BackendBaseUrl/api/db/health"
  if ($dbHealth.database -ne "reachable") {
    throw "Database health check failed."
  }

  $query = [Uri]::EscapeDataString($TermKetoprofen)
  $search = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/drugs/search?q=$query&limit=1"
  $drug = @($search.items)[0]
  if ($null -eq $drug -or -not $drug.productCode) {
    throw "Drug autocomplete returned no product."
  }

  $patient = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients" -Body @{
    displayName = "Smoke Test"
    ageYears = 78
    sex = "FEMALE"
  }
  $patientId = $patient.id

  $updatedPatient = Invoke-Json -Method Patch -Uri "$FrontendBaseUrl/api/patients/$patientId" -Body @{
    displayName = "Smoke Test Updated"
    ageYears = 79
    sex = "FEMALE"
  }
  if ($updatedPatient.displayName -ne "Smoke Test Updated") {
    throw "Patient update did not persist."
  }

  $medication = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients/$patientId/medications" -Body @{
    categoryName = $CategoryInternal
    enteredDrugName = $drug.productName
    productCode = $drug.productCode
    itemSeq = $drug.itemSeq
    durationDays = 10
    dosesPerDay = 1
    doseAmount = 1
    doseUnit = $DoseUnitTablet
  }

  $updatedMedication = Invoke-Json -Method Patch -Uri "$FrontendBaseUrl/api/medications/$($medication.id)" -Body @{
    categoryName = $CategorySurgery
    durationDays = 14
    dosesPerDay = 2
    doseAmount = 0.5
    doseUnit = $DoseUnitTablet
  }
  if ([int]$updatedMedication.durationDays -ne 14) {
    throw "Medication update did not return the changed duration."
  }

  Invoke-Json -Method Delete -Uri "$FrontendBaseUrl/api/medications/$($medication.id)" | Out-Null
  $medicationsAfterDelete = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/medications"
  if (@($medicationsAfterDelete.items).Count -ne 0) {
    throw "Deleted medication is still visible in active medication list."
  }

  $interactionA = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients/$patientId/medications" -Body @{
    categoryName = $CategoryInternal
    enteredDrugName = "Interaction sample A"
    productCode = "644902311"
    durationDays = 30
    dosesPerDay = 1
    doseAmount = 1
    doseUnit = $DoseUnitTablet
  }

  $interactionB = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients/$patientId/medications" -Body @{
    categoryName = $CategoryInternal
    enteredDrugName = "Interaction sample B"
    productCode = "645401940"
    durationDays = 30
    dosesPerDay = 1
    doseAmount = 1
    doseUnit = $DoseUnitTablet
  }

  $savedReport = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/latest"
  if ($savedReport.summary.riskCount -lt 1) {
    throw "Saved analysis report did not return the expected interaction risk."
  }
  if ($savedReport.isStale) {
    throw "Freshly saved analysis report should not be stale."
  }
  if (@($savedReport.sourceMedicationSnapshot).Count -ne 2) {
    throw "Saved analysis report did not include the medication snapshot."
  }

  $latestReport = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/latest"
  if ($latestReport.reportId -ne $savedReport.reportId) {
    throw "Latest analysis report lookup did not return the saved report."
  }
  if ($latestReport.isStale) {
    throw "Latest analysis report was unexpectedly marked stale before medication changes."
  }

  $history = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/reports?limit=5"
  if (@($history.items).Count -lt 1) {
    throw "Analysis history did not include the saved report."
  }
  if (-not @($history.items)[0].isLatest) {
    throw "Analysis history did not mark the newest report as latest."
  }
  if (@($history.items)[0].isStale) {
    throw "Analysis history marked a fresh report as stale."
  }

  $historyReport = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/reports/$(@($history.items)[0].analysisRunId)"
  if ($historyReport.reportId -ne $savedReport.reportId) {
    throw "Analysis history detail did not return the selected report."
  }

  Invoke-Json -Method Patch -Uri "$FrontendBaseUrl/api/medications/$($interactionA.id)" -Body @{
    categoryName = $CategorySurgery
    durationDays = 31
    dosesPerDay = 1
    doseAmount = 1
    doseUnit = $DoseUnitTablet
  } | Out-Null

  $staleLatestReport = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/latest"
  if (-not $staleLatestReport.isStale) {
    throw "Medication changes did not mark the latest saved report as stale."
  }

  $staleHistory = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/reports?limit=5"
  if (-not @($staleHistory.items)[0].isStale) {
    throw "Analysis history did not expose stale status after medication changes."
  }

  $refreshedReport = Invoke-Json -Method Post -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/latest"
  if ($refreshedReport.isStale) {
    throw "Refreshed analysis report should not be stale."
  }

  $refreshedHistory = Invoke-Json -Method Get -Uri "$FrontendBaseUrl/api/patients/$patientId/analysis/reports?limit=5"
  if (@($refreshedHistory.items).Count -lt 2) {
    throw "Analysis history did not retain the older report after refresh."
  }
  if (-not @($refreshedHistory.items)[0].isLatest -or @($refreshedHistory.items)[0].isStale) {
    throw "Refreshed history newest item is not the current non-stale report."
  }
  if (-not @($refreshedHistory.items)[1].isStale) {
    throw "Older history item should remain marked stale after medication changes."
  }

  Write-Host "Smoke test passed."
}
finally {
  if ($patientId) {
    try {
      Invoke-Json -Method Delete -Uri "$FrontendBaseUrl/api/patients/$patientId" | Out-Null
    }
    catch {
      Write-Warning "Cleanup failed for patient $patientId. Remove it manually if needed."
    }
  }
}
