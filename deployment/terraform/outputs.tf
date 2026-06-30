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

