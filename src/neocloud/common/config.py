from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://neocloud:neocloud_dev@localhost:5432/neocloud"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "RS256"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # AWS
    aws_region: str = "us-east-1"
    aws_eventbridge_bus: str = "neocloud-domain-events"
    aws_s3_bucket: str = "neocloud-documents"

    # App
    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "DEBUG"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
