param(
    [string]$StackName = "authclaw-direct-ec2",
    [string]$Region = "us-east-1",
    [string]$ParametersFile = "deployment/ec2/parameters.json"
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

if (-not (Test-Path $ParametersFile)) {
    throw "Missing parameter file: $ParametersFile. Copy deployment/ec2/parameters.example.json to deployment/ec2/parameters.json and fill real values."
}

$parameters = Get-Content $ParametersFile -Raw | ConvertFrom-Json
$parameterOverrides = @()
foreach ($parameter in $parameters) {
    $parameterOverrides += "$($parameter.ParameterKey)=$($parameter.ParameterValue)"
}

& $AwsCli cloudformation deploy `
    --stack-name $StackName `
    --template-file deployment/ec2/ec2-direct-cloudformation.json `
    --parameter-overrides $parameterOverrides `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $Region

& $AwsCli cloudformation describe-stacks `
    --stack-name $StackName `
    --region $Region `
    --query "Stacks[0].Outputs" `
    --output table
