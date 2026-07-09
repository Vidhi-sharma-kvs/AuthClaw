output "alb_dns_name" {
  description = "Public ALB DNS name for AuthClaw."
  value       = aws_lb.main.dns_name
}

output "backend_health_url" {
  description = "Backend readiness URL through the ALB."
  value       = "http://${aws_lb.main.dns_name}/health/ready"
}

output "frontend_url" {
  description = "Frontend URL through the ALB."
  value       = "http://${aws_lb.main.dns_name}"
}

output "document_bucket" {
  description = "S3 bucket for document storage."
  value       = aws_s3_bucket.documents.bucket
}

output "rds_endpoint" {
  description = "Private RDS PostgreSQL endpoint."
  value       = aws_db_instance.postgres.address
}

output "ecs_cluster" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "msk_bootstrap_brokers_tls" {
  description = "MSK TLS bootstrap brokers for the AuthClaw event pipeline."
  value       = var.enable_observability_pipeline ? aws_msk_cluster.observability[0].bootstrap_brokers_tls : ""
}

output "redis_primary_endpoint" {
  description = "Redis primary endpoint for distributed rate limiting and worker throttling."
  value       = var.enable_observability_pipeline ? aws_elasticache_replication_group.redis[0].primary_endpoint_address : ""
}

output "analytics_database" {
  description = "Managed analytics database used as the production ClickHouse-equivalent store."
  value       = var.enable_observability_pipeline ? aws_timestreamwrite_database.analytics[0].database_name : ""
}

output "global_authclaw_url" {
  description = "Global multi-region AuthClaw URL when Route53 DR routing is enabled."
  value       = local.multi_region_enabled ? "https://${var.global_domain_name}" : ""
}

output "documents_replica_bucket" {
  description = "Secondary-region replicated document bucket."
  value       = var.enable_multi_region_dr ? aws_s3_bucket.documents_replica[0].bucket : ""
}

output "dr_backup_vault_primary" {
  description = "Primary AWS Backup vault used for DR recovery points."
  value       = var.enable_multi_region_dr ? aws_backup_vault.primary[0].name : ""
}

output "dr_backup_vault_secondary" {
  description = "Secondary AWS Backup vault receiving cross-region backup copies."
  value       = var.enable_multi_region_dr ? aws_backup_vault.secondary[0].name : ""
}

output "dr_objectives" {
  description = "Declared DR objectives for validation and release readiness."
  value = {
    rto_minutes = var.dr_rto_minutes
    rpo_minutes = var.dr_rpo_minutes
  }
}
