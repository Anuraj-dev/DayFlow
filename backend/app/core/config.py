from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_JWT_SECRET = "change-me-in-local-env-use-a-long-random-string"
_LOCAL_ENVS = frozenset({"local", "test", "development", "dev"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+asyncpg://dayflow:dayflow@localhost:5432/dayflow"
    jwt_secret: str = PLACEHOLDER_JWT_SECRET
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"
    seed_hr_email: str = "hr@dayflow.demo"
    seed_hr_password: str = "ChangeMe_HR12!"
    seed_employee_email: str = "employee@dayflow.demo"
    seed_employee_password: str = "ChangeMe_Emp12!"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def require_secure_jwt(self) -> None:
        if self.app_env.lower() not in _LOCAL_ENVS and self.jwt_secret == PLACEHOLDER_JWT_SECRET:
            raise RuntimeError("JWT_SECRET must be set when APP_ENV is not local.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.require_secure_jwt()
    return settings
