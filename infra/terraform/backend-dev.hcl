# DEV terraform state backend (account 369607683065).
# Usage: terraform init -reconfigure -backend-config=backend-dev.hcl
bucket         = "neocloud-tfstate-369607683065"
key            = "release1/foundation/dev/terraform.tfstate"
region         = "us-east-2"
dynamodb_table = "neocloud-tflock"
encrypt        = true
