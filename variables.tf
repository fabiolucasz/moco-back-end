variable "aws_region" {
  description = "AWS Region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "database_url" {
  description = "Database connection URL (PostgreSQL / Supabase). Se fornecido, sobrescreve os campos individuais."
  type        = string
  default     = ""
  sensitive   = true
}

variable "scheme" {
  description = "Database driver scheme (e.g. postgresql+psycopg2)"
  type        = string
  default     = "postgresql+psycopg2"
}

variable "db_user" {
  description = "Database username"
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_host" {
  description = "Database host"
  type        = string
  default     = ""
}

variable "db_port" {
  description = "Database port"
  type        = string
  default     = "6543"
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "postgres"
}

variable "secret_key" {
  description = "JWT Secret Key"
  type        = string
  default     = "default-secret-key-change-in-production"
  sensitive   = true
}

variable "algorithm" {
  description = "JWT Algorithm"
  type        = string
  default     = "HS256"
}

variable "access_token_expire_minutes" {
  description = "Access token expiration minutes"
  type        = string
  default     = "15"
}

variable "refresh_token_expire_days" {
  description = "Refresh token expiration days"
  type        = string
  default     = "30"
}

variable "domain" {
  description = "Application Domain"
  type        = string
  default     = "localhost"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  default     = "redis://localhost:6379/0"
}

variable "google_client_id" {
  description = "Google OAuth Client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  default     = ""
  sensitive   = true
}
