# Infrastructure

This directory is the GitHub-facing infrastructure index.

Existing deployment assets remain in `../deployment/` to preserve CI,
documentation links, EC2 helper scripts, Terraform working directories, and
Docker validation paths.

| Area | Runtime path | Purpose |
| --- | --- | --- |
| Terraform | `../deployment/terraform/` | AWS infrastructure validation and deployable modules |
| AWS assets | `../deployment/aws/` | Production environment templates and AWS deployment notes |
| EC2 helpers | `../deployment/ec2/` | Public-IP EC2 deployment and diagnostics scripts |
| Compose | `../docker-compose.production.yml` | Production compose smoke wiring |
