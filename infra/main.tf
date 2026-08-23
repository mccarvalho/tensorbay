terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # For production, use S3 backend:
  # backend "s3" {
  #   bucket = "neocloud-terraform-state"
  #   key    = "dev/terraform.tfstate"
  #   region = "us-east-2"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = "neocloud"

  default_tags {
    tags = {
      Project     = "neocloud"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
