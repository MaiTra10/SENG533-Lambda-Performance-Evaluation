terraform {
  backend "s3" {
    bucket         = "tfstate-us-west-2-" // add bucket unique ID
    key            = "infra/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "tflock-us-west-2-" // add table unique ID
    encrypt        = true
  }
}
