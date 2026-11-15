# GitHub Actions OIDC Provider and Role

data "aws_caller_identity" "current" {}

# GitHub OIDC Provider (assumes it already exists)
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# Use existing IAM Role for GitHub Actions
data "aws_iam_role" "github_actions" {
  name = "github-oidc"
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM Role"
  value       = data.aws_iam_role.github_actions.arn
}

output "github_actions_role_name" {
  description = "Name of the GitHub Actions IAM Role"
  value       = data.aws_iam_role.github_actions.name
}
