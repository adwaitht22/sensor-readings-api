"""Request and response models (validation lives here)."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

NAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


class ReadingCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=64, pattern=NAME_PATTERN)
    sensor: str = Field(min_length=1, max_length=32, pattern=NAME_PATTERN)
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=16)
    recorded_at: datetime | None = None

    @field_validator("recorded_at")
    @classmethod
    def normalise_timezone(cls, v: datetime | None) -> datetime | None:
        """Store everything as UTC. A timestamp with no timezone is treated as UTC."""
        if v is None:
            return v
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class Reading(ReadingCreate):
    id: int
    recorded_at: datetime


class DeviceStats(BaseModel):
    device_id: str
    sensor: str | None
    count: int
    min: float
    max: float
    avg: float
    latest_value: float
    latest_recorded_at: datetime
