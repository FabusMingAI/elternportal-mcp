"""Explicit configuration; passwords never enter MCP tool arguments."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

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


class HomeAssistant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    url: str
    token_env: str = "HOME_ASSISTANT_TOKEN"
    allow_local_http: bool = False
    notify_services: list[str] = Field(default_factory=list, max_length=10)
    tts_entity: str | None = None
    media_players: list[str] = Field(default_factory=list, max_length=10)
    ai_task_entity: str | None = None
    webuntis_calendars: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_connection(self):
        u = urlsplit(self.url)
        if (
            u.scheme not in ("https", "http")
            or not u.hostname
            or u.username
            or u.password
            or u.query
            or u.fragment
            or u.path not in ("", "/")
        ):
            raise ValueError("Home Assistant URL must be an origin without credentials or query")
        if u.scheme == "http" and not self.allow_local_http:
            raise ValueError(
                "Plain HTTP requires explicit allow_local_http=true on a trusted network"
            )
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", self.token_env):
            raise ValueError("Invalid token_env")
        checks = [(s, r"notify\.[a-z0-9_]+") for s in self.notify_services]
        checks += [(s, r"media_player\.[a-z0-9_]+") for s in self.media_players]
        checks += [(s, r"calendar\.[a-z0-9_]+") for s in self.webuntis_calendars.values()]
        checks += [
            (self.tts_entity, r"tts\.[a-z0-9_]+"),
            (self.ai_task_entity, r"ai_task\.[a-z0-9_]+"),
        ]
        if any(value is not None and not re.fullmatch(pattern, value) for value, pattern in checks):
            raise ValueError("Invalid Home Assistant entity/service")
        return self


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schools: list[School] = Field(min_length=1, max_length=20)
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".local/share/elternportal-mcp")
    cache_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    lookback_days: int = Field(default=120, ge=1, le=730)
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)
    allow_pdf_downloads: bool = False
    store_original_attachments: bool = True
    appointment_kinds: list[Literal["schule", "schulaufgabe", "test"]] = Field(
        default_factory=lambda: ["schulaufgabe", "test"], max_length=3
    )
    own_class_only: bool = True
    auto_analyze_rules: bool = True
    auto_ai_analysis: bool = False
    summary_languages: list[Literal["de", "en", "es", "ca"]] = Field(
        default_factory=lambda: ["de", "en"], min_length=1, max_length=4
    )
    teacher_names: Literal["both", "name", "abbreviation"] = "both"
    timezone: str = "Europe/Berlin"
    reminder_days: list[int] = Field(default_factory=lambda: [3, 1, 0], max_length=20)
    reminder_time: str = "18:30"
    digest_time: str = "06:45"
    background_enabled: bool = False
    background_notifications: bool = False
    background_voice: bool = False
    voice_start_time: str = "07:00"
    voice_end_time: str = "20:00"
    scan_interval_seconds: int = Field(default=1800, ge=60, le=86400)
    home_assistant: HomeAssistant | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        ZoneInfo(value)
        return value

    @field_validator("reminder_time", "digest_time", "voice_start_time", "voice_end_time")
    @classmethod
    def valid_time(cls, value):
        if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
            raise ValueError("Use HH:MM")
        return value

    @field_validator("reminder_days")
    @classmethod
    def valid_days(cls, value):
        if any(d < 0 or d > 365 for d in value):
            raise ValueError("Reminder offsets must be between 0 and 365")
        return sorted(set(value), reverse=True)

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
