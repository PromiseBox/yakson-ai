param(
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

$DoseUnitTablet = New-UnicodeText @(51221)

function New-Medication {
  param(
    [Parameter(Mandatory = $true)][string]$ProductCode,
    [int]$DurationDays = 30,
    [double]$DosesPerDay = 1,
    [double]$DoseAmount = 1
  )

  @{
    enteredDrugName = $ProductCode
    productCode = $ProductCode
    durationDays = $DurationDays
    dosesPerDay = $DosesPerDay
    doseAmount = $DoseAmount
    doseUnit = $DoseUnitTablet
  }
}

function Invoke-Preview {
  param(
    [Parameter(Mandatory = $true)][object]$Patient,
    [Parameter(Mandatory = $true)][object[]]$Medications
  )

  Invoke-Json -Method Post -Uri "$BackendBaseUrl/api/analysis/preview" -Body @{
    patient = $Patient
    medications = $Medications
  }
}

function Assert-Rule {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][object]$Report,
    [Parameter(Mandatory = $true)][string]$RuleType,
    [Parameter(Mandatory = $true)][string]$Severity
  )

  $matches = @($Report.alerts | Where-Object { $_.ruleType -eq $RuleType -and $_.severity -eq $Severity })
  if ($matches.Count -lt 1) {
    $actual = @($Report.alerts | ForEach-Object { "$($_.ruleType)/$($_.severity)" }) -join ", "
    throw "$Name did not return $RuleType/$Severity. Actual: $actual"
  }
}

$DefaultPatient = @{
  displayName = "Rule Sample"
  ageYears = 78
  sex = "FEMALE"
}

$Samples = @(
  @{
    Name = "product interaction"
    Patient = $DefaultPatient
    Medications = @((New-Medication "644902311"), (New-Medication "645401940"))
    RuleType = "PRODUCT_INTERACTION"
    Severity = "RISK"
  },
  @{
    Name = "duplicate ingredient"
    Patient = $DefaultPatient
    Medications = @((New-Medication "0524 1430"), (New-Medication "73400390"))
    RuleType = "DUPLICATE_INGREDIENT"
    Severity = "CAUTION"
  },
  @{
    Name = "duplicate efficacy"
    Patient = $DefaultPatient
    Medications = @((New-Medication "665508490"), (New-Medication "6939 1570"))
    RuleType = "DUPLICATE_EFFICACY"
    Severity = "CAUTION"
  },
  @{
    Name = "elderly caution"
    Patient = $DefaultPatient
    Medications = @((New-Medication "642000510"))
    RuleType = "ELDERLY_CAUTION"
    Severity = "CAUTION"
  },
  @{
    Name = "elderly NSAID caution"
    Patient = $DefaultPatient
    Medications = @((New-Medication "648101510"))
    RuleType = "ELDERLY_CAUTION"
    Severity = "CAUTION"
  },
  @{
    Name = "age contraindication"
    Patient = @{ displayName = "Rule Sample"; ageYears = 8; sex = "UNKNOWN" }
    Medications = @((New-Medication "52400490"))
    RuleType = "AGE_CONTRAINDICATION"
    Severity = "RISK"
  },
  @{
    Name = "pregnancy caution"
    Patient = @{ displayName = "Rule Sample"; ageYears = 32; sex = "FEMALE" }
    Medications = @((New-Medication "649804410"))
    RuleType = "PREGNANCY_CAUTION"
    Severity = "RISK"
  },
  @{
    Name = "lactation caution"
    Patient = @{ displayName = "Rule Sample"; ageYears = 32; sex = "FEMALE" }
    Medications = @((New-Medication "646902211"))
    RuleType = "LACTATION_CAUTION"
    Severity = "CAUTION"
  },
  @{
    Name = "duration caution"
    Patient = $DefaultPatient
    Medications = @((New-Medication "652100640" 60))
    RuleType = "DURATION_CAUTION"
    Severity = "CAUTION"
  },
  @{
    Name = "dosage caution"
    Patient = $DefaultPatient
    Medications = @((New-Medication "689001660" 30 1 5000))
    RuleType = "DOSAGE_CAUTION"
    Severity = "CAUTION"
  }
)

foreach ($sample in $Samples) {
  $report = Invoke-Preview -Patient $sample.Patient -Medications $sample.Medications
  Assert-Rule -Name $sample.Name -Report $report -RuleType $sample.RuleType -Severity $sample.Severity
}

Write-Host "Rule sample test passed."
