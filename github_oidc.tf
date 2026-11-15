# GitHub Actions OIDC Provider and Role

data "aws_caller_identity" "current" {}

# GitHub OIDC Provider (assumes it already exists)
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# Update existing IAM Role trust policy
resource "aws_iam_role" "github_actions" {
  name = "github-oidc"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:fabiolucasz/*:*"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "finpilot"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "GitHub Actions OIDC"
  }
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM Role"
  value       = aws_iam_role.github_actions.arn
}

output "github_actions_role_name" {
  description = "Name of the GitHub Actions IAM Role"
  value       = aws_iam_role.github_actions.name
}
