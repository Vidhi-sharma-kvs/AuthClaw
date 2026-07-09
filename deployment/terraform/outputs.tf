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

