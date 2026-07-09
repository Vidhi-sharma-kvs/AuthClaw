locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  gateway_runtime_path_patterns = [
    "/api/gateway/*",
    "/gateway/*",
    "/v1/*",
    "/chat",
  ]

  api_path_patterns = [
    "/api/*",
    "/auth/*",
    "/metrics",
    "/analytics/*",
    "/audit/*",
    "/policies*",
    "/providers*",
    "/keys/*",
    "/health/*",
    "/openapi.json",
  ]

  multi_region_enabled = var.enable_multi_region_dr && var.global_hosted_zone_id != "" && var.global_domain_name != ""
  primary_dns_target   = var.primary_region_domain_name == "" ? aws_lb.main.dns_name : var.primary_region_domain_name
}
