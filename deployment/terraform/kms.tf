resource "aws_kms_key" "authclaw" {
  description             = "Customer-managed AuthClaw encryption key for secrets, documents, and audit exports"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-kms"
  })
}

resource "aws_kms_alias" "authclaw" {
  name          = "alias/${local.name_prefix}-authclaw"
  target_key_id = aws_kms_key.authclaw.key_id
}
