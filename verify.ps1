$apiKey = $env:AUTHCLAW_TEST_API_KEY
if (-not $apiKey) {
    Write-Error "AUTHCLAW_TEST_API_KEY environment variable is not set!"
    exit 1
}

$headers = @{
    "x-api-key" = $apiKey
}

Write-Host "=== START POWERSHELL VERIFICATION ==="

# 1. Upload using curl.exe
Write-Host "Uploading file..."
$uploadJson = curl.exe -s -H "x-api-key: $apiKey" -F "file=@test_security_policy.txt" http://127.0.0.1:8000/documents/upload

Write-Host "Upload response: $uploadJson"

$uploadResult = $uploadJson | ConvertFrom-Json
$docId = $uploadResult.document_id
Write-Host "Uploaded Document ID: $docId"

# 2. Analyze
$uriAnalyze = "http://127.0.0.1:8000/compliance/analyze"
$analyzePayload = @{
    document_id = $docId
} | ConvertTo-Json
$analyzeResult = Invoke-RestMethod -Uri $uriAnalyze -Method Post -Body $analyzePayload -Headers $headers -ContentType "application/json"
Write-Host "SOC2 Score: $($analyzeResult.soc2_score)%"
Write-Host "GDPR Score: $($analyzeResult.gdpr_score)%"
Write-Host "HIPAA Score: $($analyzeResult.hipaa_score)%"
Write-Host "Overall Risk: $($analyzeResult.overall_risk)"
Write-Host "Summary: $($analyzeResult.executive_summary)"

# 3. Chat
$uriChat = "http://127.0.0.1:8000/documents/chat"
$chatPayload = @{
    document_id = $docId
    question = "What is the retention period for PII?"
} | ConvertTo-Json
$chatResult = Invoke-RestMethod -Uri $uriChat -Method Post -Body $chatPayload -Headers $headers -ContentType "application/json"
Write-Host "Answer: $($chatResult.answer)"

# 4. Evidence
$uriEv = "http://127.0.0.1:8000/evidence"
$evResult = Invoke-RestMethod -Uri $uriEv -Method Get -Headers $headers
Write-Host "Total Evidence vaulted: $($evResult.Length)"

Write-Host "=== POWERSHELL VERIFICATION COMPLETE ==="
