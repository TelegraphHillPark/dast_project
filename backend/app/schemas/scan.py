from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.scan import ScanStatus
from app.models.vulnerability import VulnSeverity, VulnType


class AuthConfig(BaseModel):
    type: str = Field("none", description="none | cookie | basic | bearer | form")
    cookie: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    bearer_token: Optional[str] = None
    login_url: Optional[str] = None
    username_field: str = "username"
    password_field: str = "password"


class ScanCreate(BaseModel):
    target_url: str = Field(..., min_length=1, max_length=2048)

    @field_validator('target_url')
    @classmethod
    def target_url_must_be_http(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('target_url must start with http:// or https://')
        return v
    max_depth: int = Field(3, ge=1, le=10)
    timeout_seconds: int = Field(3600, ge=60, le=86400)
    excluded_paths: list[str] = []
    auth_config: AuthConfig = Field(default_factory=AuthConfig)


class VulnOut(BaseModel):
    id: str
    vuln_type: VulnType
    severity: VulnSeverity
    url: str
    parameter: Optional[str] = None
    method: str
    payload: Optional[str] = None
    evidence: dict
    recommendation: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanListItem(BaseModel):
    id: str
    target_url: str
    status: ScanStatus
    max_depth: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    vuln_count: int = 0

    model_config = {"from_attributes": True}


class ScanOut(BaseModel):
    id: str
    target_url: str
    status: ScanStatus
    max_depth: int
    timeout_seconds: int
    excluded_paths: list
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    vuln_count: int = 0
    vulnerabilities: list[VulnOut] = []
    crawl_stats: Optional[dict] = None

    model_config = {"from_attributes": True}
