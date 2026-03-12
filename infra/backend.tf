terraform {
  backend "s3" {
    bucket         = "tfstate-us-west-2-43262389"
    key            = "infra/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "tflock-us-west-2-43262389"
    encrypt        = true
  }
}
