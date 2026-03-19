# IAM Role
resource "aws_iam_role" "lambda-role" {

  name = "${var.function_name}-lambda-role"
  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [{
      "Action" : "sts:AssumeRole",
      "Effect" : "Allow",
      "Sid" : "",
      "Principal" : {
        "Service" : "lambda.amazonaws.com"
      }
    }]
  })

}
# Lambda Policy
resource "aws_iam_policy" "lambda-policy" {

  name = "${var.function_name}-lambda-policy"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [{
      "Effect" : "Allow",
      "Action" : var.actions,
      "Resource" : var.resources
    }]
  })

}
# Role Policy Attachment
resource "aws_iam_role_policy_attachment" "role-policy" {

  role       = aws_iam_role.lambda-role.name
  policy_arn = aws_iam_policy.lambda-policy.arn

}
# Source Code .zip Directory
locals {
  repo_root           = abspath("${path.root}/..")
  source_code_zip_dir = "${local.repo_root}/lambda/${var.path_name}/${var.zip_dir_slice}/deploy/${var.deployment_file}"
}
# Lambda Function
resource "aws_lambda_function" "lambda" {

  # Configuration
  function_name    = var.function_name
  role             = aws_iam_role.lambda-role.arn
  handler          = var.handler
  timeout          = var.timeout
  runtime          = var.runtime
  architectures    = var.architectures
  memory_size      = var.memory_size

  # Lambda code file
  filename         = local.source_code_zip_dir
  source_code_hash = filebase64sha256(local.source_code_zip_dir)

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

}

# Function URLS
resource "aws_lambda_function_url" "lambda_url" {

  function_name      = aws_lambda_function.lambda.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }

}