resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "random_id" "encryption_key" {
  byte_length = 32
}

resource "aws_secretsmanager_secret" "database_url" {
  name        = "${local.name_prefix}/database-url"
  description = "AuthClaw PostgreSQL connection string"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql://authclaw:%s@%s:5432/authclaw",
    random_password.db_password.result,
    aws_db_instance.postgres.address
  )
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "${local.name_prefix}/jwt-secret"
  description = "AuthClaw JWT signing secret"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = random_password.jwt_secret.result
}

resource "aws_secretsmanager_secret" "encryption_key" {
  name        = "${local.name_prefix}/encryption-key"
  description = "AuthClaw Fernet encryption key"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "encryption_key" {
  secret_id     = aws_secretsmanager_secret.encryption_key.id
  secret_string = replace(replace(random_id.encryption_key.b64_std, "+", "-"), "/", "_")
}

resource "aws_secretsmanager_secret" "smtp_username" {
  name        = "${local.name_prefix}/smtp-username"
  description = "SMTP username"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "smtp_username" {
  secret_id     = aws_secretsmanager_secret.smtp_username.id
  secret_string = var.smtp_username
}

resource "aws_secretsmanager_secret" "smtp_password" {
  name        = "${local.name_prefix}/smtp-password"
  description = "SMTP password or API key"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "smtp_password" {
  secret_id     = aws_secretsmanager_secret.smtp_password.id
  secret_string = var.smtp_password
}
