terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state backend.
  # Left commented so `terraform init -backend=false` works for review/validation.
  # Create the S3 bucket + DynamoDB lock table first (see README), then uncomment
  # and run `terraform init -migrate-state`.
  #
  # backend "s3" {
  #   bucket         = "neocloud-tfstate-<ACCOUNT_ID>"
  #   key            = "release1/foundation/dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "neocloud-tflock"
  #   encrypt        = true
  # }
}
