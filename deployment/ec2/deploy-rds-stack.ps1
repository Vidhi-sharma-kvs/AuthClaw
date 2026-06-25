param(
    [string]$StackName = "authclaw-rds",
    [string]$Region = "us-east-1",
    [string]$VpcId,
    [string]$PrivateSubnetIds,
    [string]$ApiTaskSecurityGroupId,
    [string]$DatabasePassword,
    [string]$DatabaseUsername = "authclaw"
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

if (-not $VpcId -or -not $PrivateSubnetIds -or -not $ApiTaskSecurityGroupId -or -not $DatabasePassword) {
    throw "Required: -VpcId, -PrivateSubnetIds, -ApiTaskSecurityGroupId, -DatabasePassword"
}

& $AwsCli cloudformation deploy `
    --stack-name $StackName `
    --template-file deployment/aws/rds-postgres-t3-small-cloudformation.json `
    --parameter-overrides `
        VpcId=$VpcId `
        PrivateSubnetIds=$PrivateSubnetIds `
        ApiTaskSecurityGroupId=$ApiTaskSecurityGroupId `
        DatabaseUsername=$DatabaseUsername `
        DatabasePassword=$DatabasePassword `
    --region $Region

& $AwsCli cloudformation describe-stacks `
    --stack-name $StackName `
    --region $Region `
    --query "Stacks[0].Outputs" `
    --output table
