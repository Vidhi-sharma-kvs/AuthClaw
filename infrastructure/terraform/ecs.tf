resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "authclaw-api"
      image     = var.api_image
      essential = true
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      environment = [
        { name = "AUTHCLAW_ENV", value = "production" },
        { name = "ENABLE_DEV_MODE", value = "false" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "AWS_SECRETS_MANAGER_ENABLED", value = "true" },
        { name = "AUTHCLAW_ALLOWED_ORIGINS", value = var.allowed_origins },
        { name = "AUTHCLAW_RATE_LIMIT_PER_MINUTE", value = "120" },
        { name = "SMTP_HOST", value = var.smtp_host },
        { name = "SMTP_FROM", value = var.smtp_from },
        { name = "SMTP_PORT", value = "587" },
        { name = "SMTP_USE_TLS", value = "true" },
        { name = "MODEL_PROVIDER", value = var.model_provider },
        { name = "MODEL_NAME", value = var.model_name },
        { name = "AUTHCLAW_DOCUMENT_STORAGE_BACKEND", value = "s3" },
        { name = "AUTHCLAW_DOCUMENT_S3_BUCKET", value = aws_s3_bucket.documents.bucket }
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
        { name = "JWT_SECRET", valueFrom = aws_secretsmanager_secret.jwt_secret.arn },
        { name = "AUTHCLAW_ENCRYPTION_KEY", valueFrom = aws_secretsmanager_secret.encryption_key.arn },
        { name = "SMTP_USERNAME", valueFrom = aws_secretsmanager_secret.smtp_username.arn },
        { name = "SMTP_PASSWORD", valueFrom = aws_secretsmanager_secret.smtp_password.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    },
    {
      name      = "authclaw-gateway"
      image     = var.gateway_image
      essential = true
      portMappings = [{
        containerPort = 9000
        protocol      = "tcp"
      }]
      environment = [
        { name = "AUTHCLAW_ENV", value = "production" },
        { name = "AUTHCLAW_GATEWAY_ADDR", value = "0.0.0.0:9000" },
        { name = "AUTHCLAW_BACKEND_URL", value = "http://127.0.0.1:8000" },
        { name = "AUTHCLAW_ALLOWED_ORIGINS", value = var.allowed_origins },
        { name = "AUTHCLAW_SECRET_BACKEND", value = "aws_secrets_manager" },
        { name = "AWS_REGION", value = var.aws_region }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.gateway.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "gateway"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://127.0.0.1:9000/health/ready || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    },
    {
      name      = "authclaw-frontend"
      image     = var.frontend_image
      essential = true
      portMappings = [{
        containerPort = 80
        protocol      = "tcp"
      }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.frontend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "frontend"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://127.0.0.1/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 10
      }
    }
  ])

  tags = local.common_tags
}

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "authclaw-api"
    container_port   = 8000
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.gateway.arn
    container_name   = "authclaw-gateway"
    container_port   = 9000
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "authclaw-frontend"
    container_port   = 80
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = true

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_execution
  ]

  tags = local.common_tags
}

