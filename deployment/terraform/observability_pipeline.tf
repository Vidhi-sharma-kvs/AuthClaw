resource "aws_msk_cluster" "observability" {
  count                  = var.enable_observability_pipeline ? 1 : 0
  cluster_name           = "${local.name_prefix}-events"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = var.msk_broker_instance_type
    client_subnets  = aws_subnet.private[*].id
    security_groups = [aws_security_group.msk[0].id]

    storage_info {
      ebs_storage_info {
        volume_size = 100
      }
    }
  }

  client_authentication {
    unauthenticated = false
    sasl {
      iam = true
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk[0].name
      }
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "msk" {
  count             = var.enable_observability_pipeline ? 1 : 0
  name              = "/aws/msk/${local.name_prefix}-events"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

resource "aws_elasticache_subnet_group" "redis" {
  count      = var.enable_observability_pipeline ? 1 : 0
  name       = "${local.name_prefix}-redis-subnets"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  count                      = var.enable_observability_pipeline ? 1 : 0
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "AuthClaw distributed rate limiting and worker throttling"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.redis[0].name
  security_group_ids         = [aws_security_group.redis[0].id]
  tags                       = local.common_tags
}

resource "aws_timestreamwrite_database" "analytics" {
  count         = var.enable_observability_pipeline ? 1 : 0
  database_name = "${replace(local.name_prefix, "-", "_")}_analytics"
  tags          = local.common_tags
}

resource "aws_timestreamwrite_table" "audit_events" {
  count         = var.enable_observability_pipeline ? 1 : 0
  database_name = aws_timestreamwrite_database.analytics[0].database_name
  table_name    = "audit_events"

  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 2555
  }

  tags = local.common_tags
}
