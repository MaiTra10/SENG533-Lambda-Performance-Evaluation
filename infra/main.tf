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
  zip_dir_slice = "experiment1"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-python-x86"

  architectures = ["x86_64"]
  runtime = "python3.13"
  handler = "main.exp1_workloads"
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
  zip_dir_slice = "experiment1"
  deployment_file = "bootstrap.zip"

  function_name = "exp1-python-arm"

  architectures = ["arm64"]
  runtime = "python3.13"
  handler = "main.exp1_workloads"
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
  zip_dir_slice = "experiment1"
  deployment_file = "x86/bootstrap.zip"

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
  zip_dir_slice = "experiment1"
  deployment_file = "arm/bootstrap.zip"

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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp1-java-x86"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp1-java-arm"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-128"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-1024"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-1769"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-x86-3008"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
#   zip_dir_slice   = "experiment1"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-x86-5307"

#   architectures = ["x86_64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
#   zip_dir_slice   = "experiment1"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-x86-10240"

#   architectures = ["x86_64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-128"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-1024"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-1769"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp2-java-arm-3008"

  architectures = ["arm64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
#   zip_dir_slice   = "experiment1"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-arm-5307"

#   architectures = ["arm64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
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
#   zip_dir_slice   = "experiment1"
#   deployment_file = "bootstrap.jar"

#   function_name = "exp2-java-arm-10240"

#   architectures = ["arm64"]
#   runtime       = "java25"
#   handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
#   memory_size   = local.exp2_memory_config_5
#   timeout       = local.exp2_timeout

#   resources = [
#     aws_s3_bucket.private_bucket.arn,
#     "${aws_s3_bucket.private_bucket.arn}/*"
#   ]
#   actions = ["s3:*"]
# }

# ============
# Experiment 3
# Cold vs Warm Start Behavior
# Reuses Experiment 1 CPU-bound matrix multiplication code
# ============

locals {
  exp3_memory_size = 1769
  exp3_timeout     = 10
}

# ============
# Python x86
# ============
module "exp3_python_x86" {
  source = "./templates/lambda"

  # Reuse Experiment 1 Python CPU-bound code
  path_name       = "python"
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.zip"

  function_name = "exp3-python-x86"

  architectures = ["x86_64"]
  runtime       = "python3.13"
  handler       = "main.exp1_workloads"
  memory_size   = local.exp3_memory_size
  timeout       = local.exp3_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]

  actions = ["s3:*"]
}

# ============
# Go x86
# ============
module "exp3_go_x86" {
  source = "./templates/lambda"

  # Reuse Experiment 1 Go CPU-bound code
  path_name       = "go"
  zip_dir_slice   = "experiment1"
  deployment_file = "x86/bootstrap.zip"

  function_name = "exp3-go-x86"

  architectures = ["x86_64"]
  runtime       = "provided.al2023"
  handler       = "main"
  memory_size   = local.exp3_memory_size
  timeout       = local.exp3_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]

  actions = ["s3:*"]
}

# ============
# Java x86
# ============
module "exp3_java_x86" {
  source = "./templates/lambda"

  # Reuse Experiment 1 Java CPU-bound code
  path_name       = "java"
  zip_dir_slice   = "experiment1"
  deployment_file = "bootstrap.jar"

  function_name = "exp3-java-x86"

  architectures = ["x86_64"]
  runtime       = "java25"
  handler       = "seng533.lambda.java.experiment1.Handler::handleRequest"
  memory_size   = local.exp3_memory_size
  timeout       = local.exp3_timeout

  resources = [
    aws_s3_bucket.private_bucket.arn,
    "${aws_s3_bucket.private_bucket.arn}/*"
  ]

  actions = ["s3:*"]
}

# Creates a text file with Lambda function URL data in the module directory /details folder
# (makes one if does not already exist)

locals {
  exp1_lambda_urls = {
    "exp1-python-x86" = module.exp1_python_x86.function_url
    "exp1-python-arm" = module.exp1_python_arm.function_url
    "exp1-go-x86"     = module.exp1_go_x86.function_url
    "exp1-go-arm"     = module.exp1_go_arm.function_url
    "exp1-java-x86"   = module.exp1_java_x86.function_url
    "exp1-java-arm"   = module.exp1_java_arm.function_url
  }

  exp2_lambda_urls = {
    "exp2-java-x86-128"  = module.exp2_java_x86_128.function_url
    "exp2-java-x86-1024" = module.exp2_java_x86_1024.function_url
    "exp2-java-x86-1769" = module.exp2_java_x86_1769.function_url
    "exp2-java-x86-3008" = module.exp2_java_x86_3008.function_url

    "exp2-java-arm-128"  = module.exp2_java_arm_128.function_url
    "exp2-java-arm-1024" = module.exp2_java_arm_1024.function_url
    "exp2-java-arm-1769" = module.exp2_java_arm_1769.function_url
    "exp2-java-arm-3008" = module.exp2_java_arm_3008.function_url
  }

    exp3_lambda_urls = {
    "exp3-python-x86" = module.exp3_python_x86.function_url
    "exp3-go-x86"     = module.exp3_go_x86.function_url
    "exp3-java-x86"   = module.exp3_java_x86.function_url
  }
}



locals {
  all_lambda_urls = {
    exp1 = local.exp1_lambda_urls
    exp2 = local.exp2_lambda_urls
    exp3 = local.exp3_lambda_urls
  }
}

# Source: ChatGPT
resource "local_file" "lambda_urls" {
  filename = "${path.module}/details/lambda_function_urls.json"

  content = <<EOT
{
  "exp1": {
${join(",\n", [
  for k, v in local.exp1_lambda_urls :
  "    \"${k}\": \"${v}\""
])}
  },
  "exp2": {
${join(",\n", [
  for k, v in local.exp2_lambda_urls :
  "    \"${k}\": \"${v}\""
])}
  },
  "exp3": {
${join(",\n", [
  for k, v in local.exp3_lambda_urls :
  "    \"${k}\": \"${v}\""
])}
  }
}
EOT
}