output "function_name" {
  value = aws_lambda_function.lambda.function_name
}
output "arn" {
  value = aws_lambda_function.lambda.arn
}

output "invoke_arn" {
  value = aws_lambda_function.lambda.invoke_arn
}

output "function_url" {
  value = aws_lambda_function_url.lambda_url.function_url
}