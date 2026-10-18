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

  # Remote state backend (S3 + DynamoDB lock). Partial configuration: the
  # concrete bucket/key/region/table are supplied per-environment via a
  # -backend-config file (backend-dev.hcl / backend-prod.hcl) so each AWS
  # account keeps its own isolated state. Run e.g.:
  #   terraform init -reconfigure -backend-config=backend-dev.hcl
  backend "s3" {}
}
