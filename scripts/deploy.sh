#!/bin/bash
set -euo pipefail

# Deploy NeoCloud API to AWS ECS
# Usage: ./deploy.sh [--init]

REGION="us-east-2"
PROJECT="neocloud"
ENV="dev"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="${PROJECT_DIR}/infra"

echo "=== NeoCloud Deploy ==="
echo "Region: ${REGION}"
echo "Environment: ${ENV}"
echo ""

# Step 1: Terraform (if --init flag)
if [[ "${1:-}" == "--init" ]]; then
    echo ">>> Initializing Terraform..."
    cd "$INFRA_DIR"
    terraform init
    echo ""
    echo ">>> Planning infrastructure..."
    terraform plan -out=tfplan
    echo ""
    read -p "Apply this plan? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        terraform apply tfplan
    else
        echo "Aborted."
        exit 1
    fi
    cd "$PROJECT_DIR"
    echo ""
fi

# Step 2: Get ECR repository URL
ECR_URL=$(cd "$INFRA_DIR" && terraform output -raw ecr_repository_url 2>/dev/null)
if [[ -z "$ECR_URL" ]]; then
    echo "ERROR: Could not get ECR URL. Run './deploy.sh --init' first."
    exit 1
fi

echo ">>> ECR Repository: ${ECR_URL}"

# Step 3: Login to ECR
echo ">>> Logging into ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_URL"

# Step 4: Build Docker image
echo ">>> Building Docker image..."
cd "$PROJECT_DIR"
docker build -t "${PROJECT}-api:latest" .

# Step 5: Tag and push
echo ">>> Pushing image..."
docker tag "${PROJECT}-api:latest" "${ECR_URL}:latest"
docker tag "${PROJECT}-api:latest" "${ECR_URL}:$(git rev-parse --short HEAD)"
docker push "${ECR_URL}:latest"
docker push "${ECR_URL}:$(git rev-parse --short HEAD)"

# Step 6: Force new ECS deployment
echo ">>> Deploying to ECS..."
CLUSTER="${PROJECT}-${ENV}"
SERVICE="${PROJECT}-${ENV}-api"
aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --force-new-deployment \
    --region "$REGION" \
    --no-cli-pager

echo ""
echo ">>> Deployment triggered! Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster "$CLUSTER" \
    --services "$SERVICE" \
    --region "$REGION"

# Step 7: Show API URL
API_URL=$(cd "$INFRA_DIR" && terraform output -raw api_url)
echo ""
echo "=== Deploy Complete ==="
echo "API URL: ${API_URL}"
echo "Health:  ${API_URL}/health"
echo "Docs:    ${API_URL}/docs"
