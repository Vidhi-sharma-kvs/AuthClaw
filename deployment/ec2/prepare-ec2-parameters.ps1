param(
    [string]$Region = "us-east-1",
    [string]$KeyName,
    [string]$InstanceType = "t3.small",
    [string]$RootVolumeGiB = "30",
    [string]$OutputFile = "deployment/ec2/parameters.json"
)

$ErrorActionPreference = "Stop"

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

$AwsCli = Resolve-AwsCli

if (-not $KeyName) {
    throw "Required: -KeyName <existing-ec2-keypair-name>"
}

if ($InstanceType -notin @("t3.small", "t3.medium")) {
    throw "InstanceType must be t3.small or t3.medium."
}

Write-Host "Checking AWS CLI access in region $Region..."
& $AwsCli sts get-caller-identity --region $Region | Out-Null

Write-Host "Finding default VPC..."
$vpcId = & $AwsCli ec2 describe-vpcs `
    --region $Region `
    --filters "Name=is-default,Values=true" `
    --query "Vpcs[0].VpcId" `
    --output text

if (-not $vpcId -or $vpcId -eq "None") {
    throw "No default VPC found in $Region. Create a VPC first or edit deployment/ec2/parameters.json manually."
}

Write-Host "Finding a public subnet in $vpcId..."
$publicSubnetId = & $AwsCli ec2 describe-subnets `
    --region $Region `
    --filters "Name=vpc-id,Values=$vpcId" "Name=map-public-ip-on-launch,Values=true" `
    --query "Subnets[0].SubnetId" `
    --output text

if (-not $publicSubnetId -or $publicSubnetId -eq "None") {
    throw "No public subnet with auto-assign public IP found in $vpcId."
}

Write-Host "Finding latest Ubuntu 24.04 LTS AMI..."
$ubuntuAmiId = & $AwsCli ssm get-parameter `
    --region $Region `
    --name "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id" `
    --query "Parameter.Value" `
    --output text

if (-not $ubuntuAmiId -or $ubuntuAmiId -eq "None") {
    throw "Could not resolve Ubuntu 24.04 LTS AMI ID from SSM."
}

Write-Host "Detecting your public IP for locked-down security group access..."
$clientIp = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
$allowedClientCidr = "$clientIp/32"

$parameters = @(
    @{ ParameterKey = "VpcId"; ParameterValue = $vpcId },
    @{ ParameterKey = "PublicSubnetId"; ParameterValue = $publicSubnetId },
    @{ ParameterKey = "KeyName"; ParameterValue = $KeyName },
    @{ ParameterKey = "AllowedClientCidr"; ParameterValue = $allowedClientCidr },
    @{ ParameterKey = "InstanceType"; ParameterValue = $InstanceType },
    @{ ParameterKey = "UbuntuAmiId"; ParameterValue = $ubuntuAmiId },
    @{ ParameterKey = "RootVolumeGiB"; ParameterValue = "$RootVolumeGiB" }
)

$outputDirectory = Split-Path -Parent $OutputFile
if ($outputDirectory -and -not (Test-Path $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$parameters | ConvertTo-Json -Depth 4 | Set-Content -Path $OutputFile -Encoding UTF8

Write-Host ""
Write-Host "Created $OutputFile"
Write-Host ""
Write-Host "Values:"
Write-Host "  VPC:              $vpcId"
Write-Host "  Public subnet:    $publicSubnetId"
Write-Host "  Key pair:         $KeyName"
Write-Host "  Allowed CIDR:     $allowedClientCidr"
Write-Host "  Instance type:    $InstanceType"
Write-Host "  Ubuntu AMI:       $ubuntuAmiId"
Write-Host "  Root volume GiB:  $RootVolumeGiB"
Write-Host ""
Write-Host "Next command:"
Write-Host ".\deployment\ec2\deploy-ec2-stack.ps1 -Region $Region -ParametersFile $OutputFile"
