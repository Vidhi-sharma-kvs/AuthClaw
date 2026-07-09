resource "aws_route53_health_check" "primary_region" {
  count             = local.multi_region_enabled ? 1 : 0
  fqdn              = local.primary_dns_target
  port              = 443
  type              = "HTTPS"
  resource_path     = var.global_health_check_path
  failure_threshold = 3
  request_interval  = 30

  tags = merge(local.common_tags, {
    Name         = "${local.name_prefix}-primary-health"
    RegionRole   = var.regional_role
    FailoverTier = "primary"
  })
}

resource "aws_route53_health_check" "secondary_region" {
  count             = local.multi_region_enabled && var.secondary_region_domain_name != "" ? 1 : 0
  fqdn              = var.secondary_region_domain_name
  port              = 443
  type              = "HTTPS"
  resource_path     = var.global_health_check_path
  failure_threshold = 3
  request_interval  = 30

  tags = merge(local.common_tags, {
    Name         = "${local.name_prefix}-secondary-health"
    RegionRole   = "secondary"
    FailoverTier = "secondary"
  })
}

resource "aws_route53_record" "global_primary" {
  count   = local.multi_region_enabled ? 1 : 0
  zone_id = var.global_hosted_zone_id
  name    = var.global_domain_name
  type    = "CNAME"
  ttl     = 30
  records = [local.primary_dns_target]

  weighted_routing_policy {
    weight = 100
  }

  set_identifier  = "${var.aws_region}-active"
  health_check_id = aws_route53_health_check.primary_region[0].id
}

resource "aws_route53_record" "global_secondary" {
  count   = local.multi_region_enabled && var.secondary_region_domain_name != "" ? 1 : 0
  zone_id = var.global_hosted_zone_id
  name    = var.global_domain_name
  type    = "CNAME"
  ttl     = 30
  records = [var.secondary_region_domain_name]

  weighted_routing_policy {
    weight = 100
  }

  set_identifier  = "${var.secondary_region}-active"
  health_check_id = aws_route53_health_check.secondary_region[0].id
}

resource "aws_s3_bucket" "documents_replica" {
  count         = var.enable_multi_region_dr ? 1 : 0
  provider      = aws.secondary
  bucket_prefix = "${local.name_prefix}-documents-replica-"
  force_destroy = false

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-documents-replica"
    Region    = var.secondary_region
    DRPurpose = "object-replication"
  })
}

resource "aws_s3_bucket_public_access_block" "documents_replica" {
  count                   = var.enable_multi_region_dr ? 1 : 0
  provider                = aws.secondary
  bucket                  = aws_s3_bucket.documents_replica[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents_replica" {
  count    = var.enable_multi_region_dr ? 1 : 0
  provider = aws.secondary
  bucket   = aws_s3_bucket.documents_replica[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents_replica" {
  count    = var.enable_multi_region_dr ? 1 : 0
  provider = aws.secondary
  bucket   = aws_s3_bucket.documents_replica[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_iam_role" "s3_replication" {
  count = var.enable_multi_region_dr ? 1 : 0
  name  = "${local.name_prefix}-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "s3_replication" {
  count = var.enable_multi_region_dr ? 1 : 0
  name  = "${local.name_prefix}-s3-replication"
  role  = aws_iam_role.s3_replication[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = [aws_s3_bucket.documents.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersion",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionTagging"
        ]
        Resource = ["${aws_s3_bucket.documents.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = ["${aws_s3_bucket.documents_replica[0].arn}/*"]
      }
    ]
  })
}

resource "aws_s3_bucket_replication_configuration" "documents" {
  count      = var.enable_multi_region_dr ? 1 : 0
  depends_on = [aws_s3_bucket_versioning.documents, aws_s3_bucket_versioning.documents_replica]
  role       = aws_iam_role.s3_replication[0].arn
  bucket     = aws_s3_bucket.documents.id

  rule {
    id     = "documents-cross-region-replication"
    status = "Enabled"

    filter {
      prefix = ""
    }

    destination {
      bucket        = aws_s3_bucket.documents_replica[0].arn
      storage_class = "STANDARD"
    }

    delete_marker_replication {
      status = "Enabled"
    }
  }
}

resource "aws_backup_vault" "primary" {
  count = var.enable_multi_region_dr ? 1 : 0
  name  = "${local.name_prefix}-backup-primary"

  tags = local.common_tags
}

resource "aws_backup_vault" "secondary" {
  count    = var.enable_multi_region_dr ? 1 : 0
  provider = aws.secondary
  name     = "${local.name_prefix}-backup-secondary"

  tags = local.common_tags
}

resource "aws_backup_plan" "dr" {
  count = var.enable_multi_region_dr ? 1 : 0
  name  = "${local.name_prefix}-dr-backup-plan"

  rule {
    rule_name         = "daily-cross-region-copy"
    target_vault_name = aws_backup_vault.primary[0].name
    schedule          = "cron(0 5 * * ? *)"
    start_window      = 60
    completion_window = 240

    lifecycle {
      delete_after = var.backup_copy_retention_days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary[0].arn

      lifecycle {
        delete_after = var.backup_copy_retention_days
      }
    }
  }

  tags = merge(local.common_tags, {
    RTO = tostring(var.dr_rto_minutes)
    RPO = tostring(var.dr_rpo_minutes)
  })
}

resource "aws_iam_role" "backup" {
  count = var.enable_multi_region_dr ? 1 : 0
  name  = "${local.name_prefix}-backup-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "backup.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "backup" {
  count      = var.enable_multi_region_dr ? 1 : 0
  role       = aws_iam_role.backup[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_backup_selection" "dr" {
  count        = var.enable_multi_region_dr ? 1 : 0
  iam_role_arn = aws_iam_role.backup[0].arn
  name         = "${local.name_prefix}-dr-resources"
  plan_id      = aws_backup_plan.dr[0].id

  resources = [
    aws_db_instance.postgres.arn,
    aws_s3_bucket.documents.arn,
  ]
}
