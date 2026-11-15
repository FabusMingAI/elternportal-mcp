"""Explicit configuration; passwords never enter MCP tool arguments."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class School(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    school: str
    username: str = ""
    password_env: str = ""

    @field_validator("school")
    @classmethod
    def validate_school(cls, value: str) -> str:
        value = value.strip().lower()
        if "://" in value:
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or url.username
                or url.password
                or url.port
                or not re.fullmatch(
                    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.eltern-portal\.org", url.hostname or ""
                )
            ):
                raise ValueError("Use a school code or https://SCHOOL.eltern-portal.org")
            value = url.hostname.split(".")[0]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
            raise ValueError("Invalid school code")
        return value

    @field_validator("password_env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", value):
            raise ValueError("password_env must name an environment variable")
        return value

    def password(self) -> SecretStr:
        value = os.environ.get(self.password_env, "") if self.password_env else ""
        if self.school != "demo" and (not self.username or not value):
            raise ValueError(f"Credentials missing for school {self.school}")
        return SecretStr(value)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schools: list[School] = Field(min_length=1, max_length=20)
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".local/share/elternportal-mcp")
    cache_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    lookback_days: int = Field(default=120, ge=1, le=730)
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)
    allow_pdf_downloads: bool = False

    @model_validator(mode="after")
    def unique_schools(self):
        codes = [s.school for s in self.schools]
        if len(codes) != len(set(codes)):
            raise ValueError("Configure each school once")
        return self


def load_settings(path: Path | None = None, *, demo: bool = False) -> Settings:
    if demo:
        return Settings(
            schools=[School(school="demo")],
            data_dir=Path(
                os.environ.get(
                    "ELTERNPORTAL_DEMO_DATA_DIR",
                    str(Path.home() / ".local/share/elternportal-mcp-demo"),
                )
            ),
        )
    if path is None:
        env_path = os.environ.get("ELTERNPORTAL_CONFIG")
        path = (
            Path(env_path).expanduser()
            if env_path
            else Path.home() / ".config/elternportal-mcp/config.json"
        )
    return Settings.model_validate(json.loads(path.read_text(encoding="utf-8")))
