from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal

Category = Literal["productive", "neutral", "non_productive"]
class Register(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    department: str = Field(default="", max_length=120)

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Enter your full name")
        return v

class Login(BaseModel):
    email: EmailStr
    password: str

class RuleInput(BaseModel):
    pattern: str = Field(min_length=2, max_length=120)
    category: Category
    enabled: bool = True

    @field_validator("pattern")
    @classmethod
    def clean_pattern(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Pattern must not be blank")
        return v

class SettingsPatch(BaseModel):
    idle_threshold: int | None = Field(default=None, ge=30, le=3600)
    poll_interval: int | None = Field(default=None, ge=3, le=5)
    auto_start: bool | None = None
    break_reminder_minutes: int | None = Field(default=None, ge=0, le=240)
    daily_goal_minutes: int | None = Field(default=None, ge=30, le=1440)
    theme: Literal["light", "dark"] | None = None
