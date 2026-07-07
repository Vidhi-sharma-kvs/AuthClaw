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
}
