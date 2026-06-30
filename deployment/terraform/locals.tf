locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  api_path_patterns = [
    "/api/*",
    "/auth/*",
    "/gateway/*",
    "/v1/*",
    "/chat",
    "/metrics",
    "/analytics/*",
    "/audit/*",
    "/policies*",
    "/providers*",
    "/keys/*",
    "/health/*",
    "/openapi.json",
  ]
}
