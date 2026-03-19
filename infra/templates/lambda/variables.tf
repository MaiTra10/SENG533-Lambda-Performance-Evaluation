# ----------------
# Role permissions
# ----------------
variable "actions" {
  type        = list(string)
  description = "A list of IAM actions that the Lambda function's policy will allow."
}
variable "resources" {
  type        = list(string)
  description = "A list of AWS resource ARNs that the Lambda function's policy can access."
}

# ----------------------------
# Lambda Configuration Options
# ----------------------------

variable "function_name" {
  type        = string
  description = "The name of the AWS Lambda function to be created."
}
variable "handler" {
  type        = string
  description = "Lambda handler (runtime dependent)."
}
variable "timeout" {
  type        = number
  description = "Lambda function timeout in seconds (default is 3s)."
  default     = 3
}
variable "path_name" {
  type        = string
  description = "Name of the path inside of ./lambda (python, java, go)."
}
variable "zip_dir_slice" {
  type        = string
  description = "The relative directory path to the source code of the Lambda function which will have the deployment zip file (<zip_dir_slice>/deploy/bootstrap.zip)."
}
variable "deployment_file" {
  type        = string
  description = "The file  to be deployed."
}
variable "runtime" {
  type        = string
  description = "Lambda runtime identifier (e.g., provided.al2, nodejs20.x, python3.12)."
}
variable "architectures" {
  type        = list(string)
  description = "Instruction set architecture for the Lambda function. Valid values: [x86_64], [arm64]."
}
variable "memory_size" {
  type        = number
  description = "Amount of memory in MB your Lambda function can use at runtime (128MB - 32768MB)."
  default     = 128
}
variable "environment_variables" {
  type        = map(string)
  description = "A map of environment variables to set for the Lambda function."
  default     = {}
}
