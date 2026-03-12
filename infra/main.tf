resource "aws_s3_bucket" "private_bucket" {
  bucket = "seng533-lambda-performance-evaluation-assets"
}

resource "aws_s3_bucket_public_access_block" "private_bucket_block" {
  bucket = aws_s3_bucket.private_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda infrastructure

# Experiment 1

# Python
# x86
module "exp1_python_x86" {
  source = "./templates/lambda"

  path_name = "python"
  zip_dir_slice = "placeholder"

  function_name = "exp1-python-x86"

  architectures = ["x86_64"]
  runtime = "python3.13"
  handler = "main.exp1_x86"
  timeout = 10

  memory_size = 1769

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ARM
module "exp1_python_arm" {
  source = "./templates/lambda"

  path_name = "python"
  zip_dir_slice = "placeholder"

  function_name = "exp1-python-arm"

  architectures = ["arm64"]
  runtime = "python3.13"
  handler = "main.exp1_x86"
  timeout = 10

  memory_size = 1769

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}

# Go
# x86
module "exp1_go_x86" {
  source = "./templates/lambda"

  path_name = "go"
  zip_dir_slice = "placeholder-x86"

  function_name = "exp1-go-x86"

  architectures = ["x86_64"]
  runtime = "provided.al2023"
  handler = "main"
  timeout = 10

  memory_size = 1769

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ARM
module "exp1_go_arm" {
  source = "./templates/lambda"

  path_name = "go"
  zip_dir_slice = "placeholder-arm"

  function_name = "exp1-go-arm"

  architectures = ["arm64"]
  runtime = "provided.al2023"
  handler = "main"
  timeout = 10

  memory_size = 1769

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}