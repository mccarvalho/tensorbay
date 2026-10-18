# PROD terraform state backend (account 104005344884).
# Usage (PROD creds in the environment):
#   terraform init -reconfigure -backend-config=backend-prod.hcl
bucket         = "neocloud-tfstate-104005344884"
key            = "release1/foundation/prod/terraform.tfstate"
region         = "us-east-2"
dynamodb_table = "neocloud-tflock"
encrypt        = true
