# AuthClaw Direct EC2 Testing Deployment

This deployment path is for testing without DNS, Route53, CloudFront, or ALB. It exposes direct EC2 endpoints:

- Frontend: `http://<frontend-ec2-public-ip>`
- Backend API: `http://<backend-ec2-public-ip>:8000`

For the lowest friction test, both frontend and backend can run on one EC2 instance. For a production-like pilot, RDS PostgreSQL should use `db.t3.small`. If you are intentionally skipping RDS, use the local PostgreSQL deployment path below.

## Architecture

```text
Browser
  -> EC2 public IP port 80
  -> Nginx static frontend
  -> Frontend calls http://<ec2-public-ip>:8000
  -> FastAPI AuthClaw Gateway on EC2 port 8000
  -> PostgreSQL
       - local EC2 PostgreSQL for no-RDS testing
       - RDS PostgreSQL db.t3.small for pilot production
  -> Customer LLM providers
```

## Security Group Rules

Testing from your laptop only:

| Resource | Inbound |
| --- | --- |
| EC2 | TCP 22 from your IP |
| EC2 | TCP 80 from your IP |
| EC2 | TCP 8000 from your IP |
| RDS | TCP 5432 from EC2 security group only |

Do not open RDS to the internet.

## Step 0 - Preflight

Before creating AWS resources, verify that AWS CLI access, deployment templates, and SendGrid email delivery are ready:

```powershell
.\deployment\ec2\preflight-check.ps1 `
  -Region us-east-1 `
  -SendGridApiKey "SG.xxxxx" `
  -SendGridFromEmail "verified-sender@example.com" `
  -SendGridToEmail "your-test-inbox@example.com"
```

If you only want to validate local deployment files and AWS identity without sending email:

```powershell
.\deployment\ec2\preflight-check.ps1 -Region us-east-1
```

Do not continue to EC2/RDS until the SendGrid test email arrives. Registration depends on this email verification path.

## Step 1 - Launch EC2

Recommended test instance:

```text
Ubuntu 24.04 LTS
t3.small or t3.medium
20-30 GB gp3 EBS
```

`t3.small` is usually enough for a pilot test. Use `t3.medium` if frontend builds are slow.

Copy the example parameters file and fill it:

```powershell
Copy-Item deployment\ec2\parameters.example.json deployment\ec2\parameters.json
notepad deployment\ec2\parameters.json
```

Or generate it automatically from AWS CLI:

```powershell
.\deployment\ec2\prepare-ec2-parameters.ps1 `
  -Region us-east-1 `
  -KeyName your-ec2-keypair-name `
  -InstanceType t3.small
```

This creates:

```text
deployment/ec2/parameters.json
```

It detects:

- default VPC
- public subnet
- latest Ubuntu 24.04 AMI
- your current public IP as `/32`
- selected key pair
- selected instance type

Only `KeyName` must be supplied because AWS cannot safely guess which SSH key pair you want to use. If you do not already have one, create it in the EC2 console before running the script.

Deploy the direct EC2 test host:

```powershell
.\deployment\ec2\deploy-ec2-stack.ps1 `
  -Region us-east-1 `
  -ParametersFile deployment/ec2/parameters.json
```

The stack outputs:

```text
FrontendUrl
BackendHealthUrl
PublicIp
Ec2SecurityGroupId
```

Save `Ec2SecurityGroupId`; the RDS stack uses it to allow database traffic from this EC2 host only.

## Step 2 - Database

### Option A - Skip RDS and Use Local PostgreSQL on EC2

Use this for direct EC2 testing only. It keeps cost and setup lower, but the database is tied to the EC2 instance lifecycle.

After EC2 is running and SendGrid is ready, deploy AuthClaw to the existing EC2 host with local PostgreSQL:

```powershell
.\deployment\ec2\deploy-app-to-ec2.ps1 `
  -Ec2PublicIp <ec2-public-ip> `
  -SshKeyPath C:\path\to\authclaw-key.pem `
  -DatabasePassword "replace-with-strong-local-postgres-password" `
  -SmtpPassword "replace-with-sendgrid-api-key" `
  -SmtpFrom "verified-sender@example.com"
```

This command:

- generates backend/frontend env files
- sets `DATABASE_URL` to local PostgreSQL on EC2
- copies the AuthClaw source bundle to EC2
- installs Ubuntu packages, Node.js, Python, Nginx, and PostgreSQL
- creates the local PostgreSQL user/database
- builds the frontend
- starts the FastAPI backend on port `8000`
- serves the frontend through Nginx on port `80`

Then verify:

```text
http://<ec2-public-ip>
http://<ec2-public-ip>:8000/health/ready
```

### Option B - Create RDS db.t3.small

Use the AWS template:

```text
deployment/aws/rds-postgres-t3-small-cloudformation.json
```

From PowerShell on your machine, use the `Ec2SecurityGroupId` output from Step 1:

```powershell
.\deployment\ec2\deploy-rds-stack.ps1 `
  -Region us-east-1 `
  -VpcId vpc-xxxxxxxx `
  -PrivateSubnetIds subnet-private-a,subnet-private-b `
  -ApiTaskSecurityGroupId sg-from-ec2-stack-output `
  -DatabasePassword "replace-with-strong-password"
```

After it creates the DB, prepare:

```text
DATABASE_URL=postgresql://authclaw:<password>@<rds-endpoint>:5432/authclaw
```

## Step 3 - Configure SendGrid Email

AuthClaw uses email delivery for tenant registration verification. For this direct EC2 test, use SendGrid before continuing.

In SendGrid:

1. Create a SendGrid API key with **Mail Send** permission.
2. Verify a **Single Sender** email address.
3. Keep the sender email exactly the same as the verified SendGrid sender.

No DNS is required for SendGrid Single Sender Verification. SendGrid domain authentication can be added later when you own a production domain.

Test SendGrid SMTP from your local machine before generating the EC2 env files:

```powershell
.\deployment\ec2\test-sendgrid-smtp.ps1 `
  -SendGridApiKey "SG.xxxxx" `
  -FromEmail "verified-sender@example.com" `
  -ToEmail "your-test-inbox@example.com"
```

If this test email does not arrive, fix SendGrid first. Registration email verification will not work until SMTP delivery works.

You can generate the backend and frontend runtime env files automatically:

```powershell
.\deployment\ec2\generate-runtime-env.ps1 `
  -Ec2PublicIp <ec2-public-ip> `
  -RdsEndpoint <rds-endpoint> `
  -DatabasePassword "replace-with-rds-password" `
  -SmtpPassword "replace-with-sendgrid-api-key" `
  -SmtpFrom "verified-sender@example.com"
```

For local PostgreSQL on EC2 without RDS:

```powershell
.\deployment\ec2\generate-runtime-env.ps1 `
  -Ec2PublicIp <ec2-public-ip> `
  -UseLocalPostgres `
  -DatabasePassword "replace-with-local-postgres-password" `
  -SmtpPassword "replace-with-sendgrid-api-key" `
  -SmtpFrom "verified-sender@example.com"
```

This creates:

```text
deployment/ec2/generated/backend.env
deployment/ec2/generated/frontend.env.production
```

These generated files contain secrets and are ignored by `.gitignore`.

After the repository is present on EC2, copy generated env files to the server:

```powershell
.\deployment\ec2\copy-runtime-env-to-ec2.ps1 `
  -Ec2PublicIp <ec2-public-ip> `
  -SshKeyPath C:\path\to\your-key.pem
```

## Step 4 - Install base packages

Copy the repository to EC2, then run:

```bash
cd /path/to/AuthClaw
sudo bash deployment/ec2/install-ubuntu.sh
```

Then copy the repository contents into:

```text
/opt/authclaw
```

Example:

```bash
sudo rsync -a --delete /path/to/AuthClaw/ /opt/authclaw/
sudo chown -R authclaw:authclaw /opt/authclaw
```

## Step 5 - Configure backend environment

If you used `generate-runtime-env.ps1`, copy the generated backend env:

```bash
sudo cp /tmp/backend.env /opt/authclaw/.env
```

Otherwise copy the template manually:

```bash
sudo cp /opt/authclaw/deployment/ec2/backend.env.template /opt/authclaw/.env
sudo nano /opt/authclaw/.env
```

Fill these values:

```env
AUTHCLAW_ALLOWED_ORIGINS=http://<ec2-public-ip>
DATABASE_URL=postgresql://authclaw:<password>@<rds-endpoint>:5432/authclaw
JWT_SECRET=<32+ character secret>
AUTHCLAW_ENCRYPTION_KEY=<Fernet key>
SMTP_HOST=<smtp-host>
SMTP_USERNAME=<smtp-username>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM=<sender-email>
```

For SendGrid, use:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_USERNAME=apikey
SMTP_PASSWORD=<sendgrid-api-key>
SMTP_FROM=<verified-sendgrid-sender-email>
SMTP_USE_TLS=true
```

For no-DNS testing only:

```env
SKIP_DOMAIN_VERIFICATION=true
```

For real customer onboarding later:

```env
SKIP_DOMAIN_VERIFICATION=false
```

## Step 6 - Configure frontend API URL

If you used `generate-runtime-env.ps1`, copy the generated frontend env:

```bash
sudo cp /tmp/frontend.env.production /opt/authclaw/frontend/.env.production
```

Otherwise create it manually:

```bash
sudo cp /opt/authclaw/deployment/ec2/frontend.env.template /opt/authclaw/frontend/.env.production
sudo nano /opt/authclaw/frontend/.env.production
```

Set:

```env
VITE_API_BASE_URL=http://<ec2-public-ip>:8000
```

## Step 7 - Start AuthClaw

Run:

```bash
cd /opt/authclaw
sudo bash deployment/ec2/setup-app.sh
```

## Step 8 - Verify

From EC2:

```bash
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1/health
```

From your laptop:

```text
http://<ec2-public-ip>
http://<ec2-public-ip>:8000/health/ready
```

## Step 9 - Product Test

1. Open `http://<ec2-public-ip>`.
2. Register tenant.
3. Verify email through SendGrid SMTP.
4. Domain verification is skipped for this no-DNS testing deployment.
5. Sign in.
6. Generate AuthClaw API key.
7. Connect provider credentials.
8. Send gateway chat.
9. Check Requests, Request Detail, and Audit Logs.

## Service Commands

Backend:

```bash
sudo systemctl status authclaw-api
sudo journalctl -u authclaw-api -f
sudo systemctl restart authclaw-api
```

Frontend:

```bash
sudo systemctl status nginx
sudo nginx -t
sudo systemctl restart nginx
```

## Notes

- This is HTTP-only testing. Do not use it for real customer production traffic.
- No DNS means real domain verification cannot work; `SKIP_DOMAIN_VERIFICATION=true` is expected here.
- Keep `DISABLE_MFA_FOR_TESTING=false` unless you intentionally need local recovery access.
- Keep RDS private and accessible only from EC2.
