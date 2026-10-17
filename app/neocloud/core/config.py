"""Application configuration loaded from environment variables.

The ECS task definition injects BEDROCK_MODEL_ID, DOCUMENTS_BUCKET,
AURORA_SECRET_ARN, GOOGLE_SSO_SECRET_ARN, COGNITO_USER_POOL_ID and
COGNITO_CLIENT_ID (see infra/terraform main.tf environment_variables).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "NeoCloud Platform"
    app_env: str = "dev"
    api_v1_prefix: str = "/v1"
    log_level: str = "INFO"

    # AWS
    aws_region: str = "us-east-2"

    # Database
    # If DATABASE_URL is set it takes precedence (useful for local/testing with
    # SQLite). Otherwise credentials are fetched from Secrets Manager using
    # aurora_secret_arn + the Aurora endpoint.
    database_url: str | None = None
    aurora_secret_arn: str | None = None
    aurora_host: str | None = None
    aurora_port: int = 5432
    aurora_database: str = "neocloud"
    db_echo: bool = False

    # Auth (Cognito)
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    # When False, auth is bypassed with a stub user (local/testing only).
    auth_enabled: bool = True

    # AI (Bedrock)
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_guardrail_id: str | None = None
    bedrock_guardrail_version: str = "DRAFT"

    # Storage
    documents_bucket: str | None = None

    @property
    def cognito_issuer(self) -> str | None:
        if not self.cognito_user_pool_id:
            return None
        return (
            f"https://cognito-idp.{self.aws_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}"
        )

    @property
    def cognito_jwks_url(self) -> str | None:
        issuer = self.cognito_issuer
        return f"{issuer}/.well-known/jwks.json" if issuer else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
