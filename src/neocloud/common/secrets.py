"""
Secrets Manager loader.

In production (APP_ENV != development), all sensitive config is loaded
from AWS Secrets Manager at startup. In development, falls back to
environment variables / .env file.

Secret paths:
    neocloud/{env}/db/master          -> DATABASE_URL, DB host/port/user/pass
    neocloud/{env}/app/config         -> JWT_SECRET_KEY, JWT_ALGORITHM, CORS_ORIGINS
    neocloud/{env}/cognito/config     -> COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID
    neocloud/{env}/infra/config       -> REDIS_URL, AWS_S3_BUCKET, AWS_EVENTBRIDGE_BUS
    neocloud/{env}/integrations/crm   -> CRM API credentials
    neocloud/{env}/integrations/erp   -> ERP API credentials
    neocloud/{env}/integrations/smtp  -> SMTP credentials
"""
import json
import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

import structlog

logger = structlog.get_logger()


@lru_cache(maxsize=32)
def get_secret(secret_name: str, region: str = "us-east-2") -> dict[str, Any]:
    """Fetch and cache a secret from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret = response.get("SecretString", "{}")
        return json.loads(secret)
    except ClientError as e:
        logger.error("failed_to_load_secret", secret=secret_name, error=str(e))
        raise


def load_secrets_to_env(env: str = "dev", region: str = "us-east-2") -> None:
    """
    Load secrets from Secrets Manager into environment variables.

    Called once at app startup when APP_ENV != 'development'.
    ECS already injects individual secret keys via the task definition,
    so this is mainly used for local testing against real secrets.
    """
    if os.getenv("APP_ENV", "development") == "development":
        logger.info("skipping_secrets_load", reason="development environment uses .env file")
        return

    prefix = f"neocloud/{env}"
    secret_map = {
        f"{prefix}/db/master": {
            "url": "DATABASE_URL",
        },
        f"{prefix}/app/config": {
            "jwt_secret_key": "JWT_SECRET_KEY",
            "jwt_algorithm": "JWT_ALGORITHM",
            "cors_origins": "CORS_ORIGINS",
            "app_debug": "APP_DEBUG",
        },
        f"{prefix}/cognito/config": {
            "user_pool_id": "COGNITO_USER_POOL_ID",
            "client_id": "COGNITO_CLIENT_ID",
            "region": "COGNITO_REGION",
        },
        f"{prefix}/infra/config": {
            "redis_url": "REDIS_URL",
            "s3_bucket": "AWS_S3_BUCKET",
            "eventbridge_bus": "AWS_EVENTBRIDGE_BUS",
        },
    }

    for secret_name, key_map in secret_map.items():
        try:
            secret_data = get_secret(secret_name, region)
            for secret_key, env_var in key_map.items():
                if secret_key in secret_data and not os.getenv(env_var):
                    os.environ[env_var] = str(secret_data[secret_key])
            logger.info("secrets_loaded", secret=secret_name)
        except Exception as e:
            logger.warning("secrets_load_failed", secret=secret_name, error=str(e))


def get_integration_secret(integration: str, env: str = "dev") -> dict[str, Any]:
    """
    Fetch credentials for a specific integration.

    Usage:
        creds = get_integration_secret("crm")
        client = SalesforceClient(api_key=creds["api_key"])
    """
    secret_name = f"neocloud/{env}/integrations/{integration}"
    return get_secret(secret_name)
