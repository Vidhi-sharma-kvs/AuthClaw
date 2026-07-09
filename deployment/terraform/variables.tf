variable "project_name" {
  description = "Name prefix for AuthClaw AWS resources."
  type        = string
  default     = "authclaw"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zones" {
  description = "Two availability zones for ALB/ECS/RDS subnet placement."
  type        = list(string)
}

variable "allowed_http_cidr_blocks" {
  description = "CIDR blocks allowed to reach the public ALB."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway so private ECS tasks can call SMTP and LLM provider APIs."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN. If empty, only HTTP listener is created."
  type        = string
  default     = ""
}

variable "api_image" {
  description = "Full ECR image URI for the AuthClaw FastAPI backend."
  type        = string
}

variable "gateway_image" {
  description = "Full ECR image URI for the AuthClaw Go gateway."
  type        = string
}

variable "frontend_image" {
  description = "Full ECR image URI for the AuthClaw frontend Nginx container."
  type        = string
}

variable "ecs_task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 1024
}

variable "ecs_task_memory" {
  description = "Fargate task memory MiB."
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Number of ECS service tasks."
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance class. t3.small is the requested baseline."
  type        = string
  default     = "db.t3.small"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "db_backup_retention_days" {
  description = "RDS automated backup retention in days."
  type        = number
  default     = 7
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "allowed_origins" {
  description = "Production CORS origins, comma-separated, for AuthClaw frontend origins."
  type        = string
}

variable "smtp_host" {
  description = "SMTP host for onboarding and MFA emails."
  type        = string
}

variable "smtp_from" {
  description = "Verified SMTP sender address."
  type        = string
}

variable "smtp_username" {
  description = "SMTP username."
  type        = string
  sensitive   = true
}

variable "smtp_password" {
  description = "SMTP password or SendGrid API key."
  type        = string
  sensitive   = true
}

variable "model_provider" {
  description = "Default fallback model provider."
  type        = string
  default     = "gemini"
}

variable "model_name" {
  description = "Default fallback model name."
  type        = string
  default     = "gemini-2.5-flash-lite"
}

variable "enable_observability_pipeline" {
  description = "Provision production Kafka/MSK, Redis rate limiting, and managed analytics storage."
  type        = bool
  default     = true
}

variable "kafka_rest_url" {
  description = "Kafka REST Proxy URL for ECS producers. Use a private MSK REST proxy or compatible endpoint."
  type        = string
  default     = ""
}

variable "msk_broker_instance_type" {
  description = "MSK broker instance type for the AuthClaw event pipeline."
  type        = string
  default     = "kafka.t3.small"
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type for distributed rate limiting and worker throttling."
  type        = string
  default     = "cache.t4g.micro"
}

variable "enable_multi_region_dr" {
  description = "Enable optional active-active DNS, cross-region object replication, and backup-copy DR controls."
  type        = bool
  default     = false
}

variable "secondary_region" {
  description = "Secondary AWS region used for DR resources and peer-region replication."
  type        = string
  default     = "us-west-2"
}

variable "regional_role" {
  description = "Role of this Terraform deployment in the active-active topology: primary or secondary."
  type        = string
  default     = "primary"

  validation {
    condition     = contains(["primary", "secondary"], var.regional_role)
    error_message = "regional_role must be either primary or secondary."
  }
}

variable "global_hosted_zone_id" {
  description = "Route53 hosted zone ID for global AuthClaw DNS. Required when enable_multi_region_dr is true."
  type        = string
  default     = ""
}

variable "global_domain_name" {
  description = "Global AuthClaw DNS name, for example app.authclaw.example.com."
  type        = string
  default     = ""
}

variable "primary_region_domain_name" {
  description = "Primary regional ALB or DNS name used as a Route53 active-active target."
  type        = string
  default     = ""
}

variable "secondary_region_domain_name" {
  description = "Secondary regional ALB or DNS name used as a Route53 active-active target."
  type        = string
  default     = ""
}

variable "global_health_check_path" {
  description = "HTTP path used by Route53 health checks and DR validation."
  type        = string
  default     = "/health/ready"
}

variable "dr_rto_minutes" {
  description = "Documented maximum recovery time objective for regional failover validation."
  type        = number
  default     = 30
}

variable "dr_rpo_minutes" {
  description = "Documented maximum recovery point objective for backup and replication validation."
  type        = number
  default     = 15
}

variable "backup_copy_retention_days" {
  description = "Retention period for cross-region backup copies."
  type        = number
  default     = 35
}
