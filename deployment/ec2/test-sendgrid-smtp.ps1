param(
    [string]$SendGridApiKey,
    [string]$FromEmail,
    [string]$ToEmail,
    [string]$SmtpHost = "smtp.sendgrid.net",
    [int]$SmtpPort = 587
)

$ErrorActionPreference = "Stop"

if (-not $SendGridApiKey) { throw "Required: -SendGridApiKey" }
if (-not $FromEmail) { throw "Required: -FromEmail. Use a SendGrid verified sender." }
if (-not $ToEmail) { throw "Required: -ToEmail" }

$message = New-Object System.Net.Mail.MailMessage
$client = $null

try {
    $message.From = $FromEmail
    $message.To.Add($ToEmail)
    $message.Subject = "AuthClaw SendGrid SMTP test"
    $message.Body = "AuthClaw SendGrid SMTP delivery succeeded at $(Get-Date -Format o)."

    $client = New-Object System.Net.Mail.SmtpClient($SmtpHost, $SmtpPort)
    $client.EnableSsl = $true
    $client.Credentials = New-Object System.Net.NetworkCredential("apikey", $SendGridApiKey)
    $client.Send($message)

    Write-Host "SendGrid SMTP test email sent."
    Write-Host "  From: $FromEmail"
    Write-Host "  To:   $ToEmail"
}
finally {
    if ($client) { $client.Dispose() }
    $message.Dispose()
}
