# IAM Policy for GitHub Actions OIDC Role

resource "aws_iam_policy" "github_actions_finpilot" {
  name        = "github-actions-finpilot-policy"
  description = "Policy for GitHub Actions to manage FinPilot infrastructure"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:*",
          "s3:*",
          "vpc:*",
          "iam:GetRole",
          "iam:PassRole",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:GetInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_actions_custom_policy" {
  role       = "github-oidc"
  policy_arn = aws_iam_policy.github_actions_finpilot.arn
}
