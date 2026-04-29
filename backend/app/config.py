from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    simulation_interval_seconds: float = 1.0
    planned_production_minutes: int = 480
    ideal_cycle_time_seconds: float = 2.4
    unit_value_dollars: float = 18.50
    operating_cost_per_hour_dollars: float = 240.0
    target_oee: float = 0.85

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
