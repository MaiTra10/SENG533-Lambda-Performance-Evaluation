resource "aws_s3_bucket" "private_bucket" {
  bucket = "seng533-rohil-aksh-1-performance-evaluation-assets"
}

resource "aws_s3_bucket_public_access_block" "private_bucket_block" {
  bucket = aws_s3_bucket.private_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda infrastructure

# ============
# Experiment 1
# ============
locals {
  exp1_memory_size = 1769
  exp1_timeout     = 10
}
# ============
# Python
# x86
# ============
module "exp1_python_x86" {
  source = "./templates/lambda"

  path_name = "python"
  zip_dir_slice = "placeholder"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-python-x86"

  architectures = ["x86_64"]
  runtime = "python3.13"
  handler = "main.exp1_x86"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ============
# ARM
# ============
module "exp1_python_arm" {
  source = "./templates/lambda"

  path_name = "python"
  zip_dir_slice = "placeholder"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-python-arm"

  architectures = ["arm64"]
  runtime = "python3.13"
  handler = "main.exp1_x86"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ============
# Go
# x86
# ============
module "exp1_go_x86" {
  source = "./templates/lambda"

  path_name = "go"
  zip_dir_slice = "placeholder-x86"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-go-x86"

  architectures = ["x86_64"]
  runtime = "provided.al2023"
  handler = "main"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ============
# ARM
# ============
module "exp1_go_arm" {
  source = "./templates/lambda"

  path_name = "go"
  zip_dir_slice = "placeholder-arm"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-go-arm"

  architectures = ["arm64"]
  runtime = "provided.al2023"
  handler = "main"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]

}
# ============
# Java
# x86
# ============
module "exp1_java_x86" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp1-java-x86"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}
# ============
# ARM
# ============
module "exp1_java_arm" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp1-java-arm"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size = local.exp1_memory_size
  timeout     = local.exp1_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

# ============
# Experiment 2
# ============
locals {
  exp2_memory_config_1 = 128
  exp2_memory_config_2 = 1024
  exp2_memory_config_3 = 1769
  # exp2_memory_config_4 = 3008
  # exp2_memory_config_5 = 3008
  exp2_timeout      = 10
}
# ============
# x86
# ============
module "exp2_java_x86_128" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-128"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_1
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

module "exp2_java_x86_1024" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-1024"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_2
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

module "exp2_java_x86_1769" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-1769"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_3
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

# NOTE; Currently do not have access to depoy Lambdas over 3GB

module "exp2_java_x86_3008" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-3008"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = 3008
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

# module "exp2_java_x86_5307" {
#   source = "./templates/lambda"

#   path_name       = "java"
#   zip_dir_slice   = "placeholder"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-x86-5307"

#   architectures = ["x86_64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
#   memory_size   = local.exp2_memory_config_4
#   timeout       = local.exp2_timeout

#   resources = [
#     aws_s3_bucket.private_bucket.arn,
#     "${aws_s3_bucket.private_bucket.arn}/*"
#   ]
#   actions = ["s3:*"]
# }

# module "exp2_java_x86_10240" {
#   source = "./templates/lambda"

#   path_name       = "java"
#   zip_dir_slice   = "placeholder"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-x86-10240"

#   architectures = ["x86_64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
#   memory_size   = local.exp2_memory_config_5
#   timeout       = local.exp2_timeout

#   resources = [
#     aws_s3_bucket.private_bucket.arn,
#     "${aws_s3_bucket.private_bucket.arn}/*"
#   ]
#   actions = ["s3:*"]
# }

# ============
# ARM
# ============
module "exp2_java_arm_128" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-128"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_1
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

module "exp2_java_arm_1024" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-1024"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_2
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

module "exp2_java_arm_1769" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-1769"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = local.exp2_memory_config_3
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

# NOTE; Currently do not have access to depoy Lambdas over 3GB

module "exp2_java_arm_3008" {
  source = "./templates/lambda"

  path_name       = "java"
  zip_dir_slice   = "placeholder"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-3008"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
  memory_size   = 3008
  timeout       = local.exp2_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]
  actions = ["s3:*"]
}

# module "exp2_java_arm_5307" {
#   source = "./templates/lambda"

#   path_name       = "java"
#   zip_dir_slice   = "placeholder"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-arm-5307"

#   architectures = ["arm64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
#   memory_size   = local.exp2_memory_config_4
#   timeout       = local.exp2_timeout

#   resources = [
#     aws_s3_bucket.private_bucket.arn,
#     "${aws_s3_bucket.private_bucket.arn}/*"
#   ]
#   actions = ["s3:*"]
# }

# module "exp2_java_arm_10240" {
#   source = "./templates/lambda"

#   path_name       = "java"
#   zip_dir_slice   = "placeholder"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-arm-10240"

#   architectures = ["arm64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.placeholder.Handler::handleRequest"
#   memory_size   = local.exp2_memory_config_5
#   timeout       = local.exp2_timeout

#   resources = [
#     aws_s3_bucket.private_bucket.arn,
#     "${aws_s3_bucket.private_bucket.arn}/*"
#   ]
#   actions = ["s3:*"]
# }
