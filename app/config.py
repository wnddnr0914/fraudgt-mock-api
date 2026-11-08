"""Validated runtime settings. Uvicorn --env-file loads a local .env when requested."""
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alert_threshold: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    fraudgt_model_version: str = Field(default="fraudgt-mock-v1", min_length=1)
    typology_model_version: str = Field(default="typology-mock-v1", min_length=1)
    graph_default_hops: int = Field(default=2, ge=1, le=3)
    graph_default_lookback_days: int = Field(default=7, ge=1, le=30)
    source_timezone: str = "UTC"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")

    @field_validator("source_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("SOURCE_TIMEZONE must be a valid IANA timezone") from exc
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        from urllib.parse import urlsplit

        for value in values:
            parsed = urlsplit(value)
            if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                    or parsed.path or parsed.query or parsed.fragment
                    or parsed.username or parsed.password):
                raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins without paths")
        return tuple(dict.fromkeys(values))

    @classmethod
    def from_env(cls) -> "Settings":
        names = {
            "ALERT_THRESHOLD": "alert_threshold",
            "FRAUDGT_MODEL_VERSION": "fraudgt_model_version",
            "TYPOLOGY_MODEL_VERSION": "typology_model_version",
            "GRAPH_DEFAULT_HOPS": "graph_default_hops",
            "GRAPH_DEFAULT_LOOKBACK_DAYS": "graph_default_lookback_days",
            "SOURCE_TIMEZONE": "source_timezone",
        }
        values = {field: os.environ[name] for name, field in names.items() if name in os.environ}
        if "CORS_ORIGINS" in os.environ:
            values["cors_origins"] = tuple(x.strip() for x in os.environ["CORS_ORIGINS"].split(",") if x.strip())
        return cls.model_validate(values)
