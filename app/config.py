"""
Application configuration.

Loads settings from environment variables (or the .env file in the project root)
and exposes them via a typed Pydantic model. Using pydantic-settings gives us:
- explicit, typed configuration surface (no stringly-typed os.getenv soup),
- validation at startup (missing required values blow up immediately),
- a single cached instance accessible from anywhere via get_settings().

Values in real environment variables take precedence over the .env file,
which is the standard "twelve-factor"-style behavior.
"""
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings populated from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Auth0 ----------------------------------------------------------------
    auth0_domain: str = Field(
        ...,
        description="Auth0 tenant domain without scheme, e.g. dev-xxx.us.auth0.com",
    )
    auth0_audience: str = Field(
        ...,
        description="API audience configured in Auth0 (must match the aud claim).",
    )
    auth0_issuer: str = Field(
        ...,
        description="Token issuer URL, usually https://<AUTH0_DOMAIN>/ (trailing slash).",
    )

    # --- Authorization --------------------------------------------------------
    # NoDecode tells pydantic-settings to skip its default JSON-decoding for
    # this complex field and hand the raw env string to our validator. Without
    # it, ADMIN_EMAILS=a@x.com,b@x.com would fail JSON parsing before our
    # mode="before" validator ever runs.
    admin_emails: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Emails allowed to perform write operations on /articles.",
    )

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_admin_emails(cls, value):
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        return value

    # --- Infrastructure -------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Comma-separated list of allowed CORS origins.",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    database_path: str = Field(
        default="fastapiblog.db",
        description="Path to the SQLite database file.",
    )

    images_dir: str = Field(
        default="images",
        description="Directory where uploaded images are stored.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings instance (parsed once)."""
    return Settings()
