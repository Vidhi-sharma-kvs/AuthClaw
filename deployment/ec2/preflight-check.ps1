param(
    [string]$Region = "us-east-1",
    [string]$ParametersFile = "deployment/ec2/parameters.json",
    [string]$SendGridApiKey = "",
    [string]$SendGridFromEmail = "",
    [string]$SendGridToEmail = ""
)

$ErrorActionPreference = "Stop"

function Write-Check($Name, $Status, $Details = "") {
    $line = "[{0}] {1}" -f $Status, $Name
    if ($Details) {
        $line = "$line - $Details"
    }
    Write-Host $line
}

function Test-JsonFile($Path) {
    if (-not (Test-Path $Path)) {
        throw "Missing JSON file: $Path"
    }

    Get-Content $Path -Raw | ConvertFrom-Json | Out-Null
}

function Test-PowerShellFile($Path) {
    if (-not (Test-Path $Path)) {
        throw "Missing PowerShell file: $Path"
    }

    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $Path),
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null

    if ($errors.Count -gt 0) {
        $messages = ($errors | ForEach-Object { $_.Message }) -join "; "
        throw "PowerShell parse failed for ${Path}: $messages"
    }
}

function Resolve-AwsCli {
    $command = Get-Command aws -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $defaultPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path $defaultPath) {
        return $defaultPath
    }

    throw "AWS CLI is not installed or not available. Install it with: winget install --id Amazon.AWSCLI -e"
}

Write-Host "AuthClaw EC2 public-IP deployment preflight"
Write-Host "Region: $Region"
Write-Host ""

$AwsCli = Resolve-AwsCli
Write-Check "AWS CLI" "OK" $AwsCli

$identity = & $AwsCli sts get-caller-identity --region $Region --output json | ConvertFrom-Json
Write-Check "AWS credentials" "OK" "Account $($identity.Account), ARN $($identity.Arn)"

Test-JsonFile "deployment/ec2/ec2-direct-cloudformation.json"
Write-Check "EC2 CloudFormation template" "OK"

Test-JsonFile "deployment/aws/rds-postgres-t3-small-cloudformation.json"
Write-Check "RDS db.t3.small CloudFormation template" "OK"

$scripts = @(
    "deployment/ec2/prepare-ec2-parameters.ps1",
    "deployment/ec2/deploy-ec2-stack.ps1",
    "deployment/ec2/deploy-rds-stack.ps1",
    "deployment/ec2/generate-runtime-env.ps1",
    "deployment/ec2/copy-runtime-env-to-ec2.ps1",
    "deployment/ec2/test-sendgrid-smtp.ps1"
)

foreach ($script in $scripts) {
    Test-PowerShellFile $script
}
Write-Check "Deployment PowerShell scripts" "OK"

if (Test-Path $ParametersFile) {
    Test-JsonFile $ParametersFile
    Write-Check "EC2 parameters file" "OK" $ParametersFile
}
else {
    Write-Check "EC2 parameters file" "MISSING" "Run deployment/ec2/prepare-ec2-parameters.ps1 before deploying EC2."
}

if ($SendGridApiKey -or $SendGridFromEmail -or $SendGridToEmail) {
    if (-not $SendGridApiKey -or -not $SendGridFromEmail -or -not $SendGridToEmail) {
        throw "SendGrid test requires -SendGridApiKey, -SendGridFromEmail, and -SendGridToEmail."
    }

    & "deployment/ec2/test-sendgrid-smtp.ps1" `
        -SendGridApiKey $SendGridApiKey `
        -FromEmail $SendGridFromEmail `
        -ToEmail $SendGridToEmail

    Write-Check "SendGrid SMTP" "OK" "Test email sent."
}
else {
    Write-Check "SendGrid SMTP" "SKIPPED" "Pass SendGrid parameters to send a real test email."
}

Write-Host ""
Write-Host "Next commands:"
Write-Host "1. Prepare EC2 parameters:"
Write-Host "   .\deployment\ec2\prepare-ec2-parameters.ps1 -Region $Region -KeyName <your-ec2-keypair-name> -InstanceType t3.small"
Write-Host "2. Deploy EC2 public-IP host:"
Write-Host "   .\deployment\ec2\deploy-ec2-stack.ps1 -Region $Region -ParametersFile $ParametersFile"
Write-Host "3. Deploy RDS db.t3.small after EC2 outputs Ec2SecurityGroupId."
