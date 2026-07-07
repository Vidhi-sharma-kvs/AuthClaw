# Infrastructure

This directory is the GitHub-facing infrastructure index and now contains a
compatibility copy of the Terraform stack under `terraform/`.

Existing deployment assets remain in `../deployment/` to preserve CI,
documentation links, EC2 helper scripts, Terraform working directories, and
Docker validation paths. Keep both locations synchronized until CI is migrated
to `infrastructure/terraform`.

| Area | Runtime path | Purpose |
| --- | --- | --- |
| Terraform | `./terraform/` and `../deployment/terraform/` | AWS infrastructure validation and deployable modules |
| AWS assets | `../deployment/aws/` | Production environment templates and AWS deployment notes |
| EC2 helpers | `../deployment/ec2/` | Public-IP EC2 deployment and diagnostics scripts |
| Compose | `../docker-compose.production.yml` | Production compose smoke wiring |

## Terraform

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
```
