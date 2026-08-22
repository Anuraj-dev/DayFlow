from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://dayflow:dayflow@localhost:5432/dayflow"
    jwt_secret: str = "change-me-in-local-env-use-a-long-random-string"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"
    seed_hr_email: str = "hr@dayflow.demo"
    seed_hr_password: str = "ChangeMe_HR12!"
    seed_employee_email: str = "employee@dayflow.demo"
    seed_employee_password: str = "ChangeMe_Emp12!"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
