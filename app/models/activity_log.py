from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActivityCategory(str, Enum):
    SCREEN = "screen"
    ACTION = "action"
    API = "api"
    ERROR = "error"
    LIFECYCLE = "lifecycle"


# Device/app snapshot sent with every batch
class ActivityDeviceInfo(BaseModel):
    platform: Optional[str] = Field(None, max_length=20)
    os_version: Optional[str] = Field(None, max_length=50)
    brand: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    is_emulator: Optional[bool] = None
    app_variant: Optional[str] = Field(None, max_length=50)
    app_version: Optional[str] = Field(None, max_length=50)
    build_version: Optional[str] = Field(None, max_length=50)
    network_type: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = Field(None, max_length=100)


class ActivityEventIn(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=100)
    category: ActivityCategory
    ts: datetime
    session_id: str = Field(..., min_length=1, max_length=64)
    seq: int = 0
    screen: Optional[str] = Field(None, max_length=100)
    duration_ms: Optional[int] = None
    # User the event was recorded for on the device (null before login)
    user_id: Optional[str] = Field(None, max_length=64)
    pre_login: bool = False
    props: Dict[str, Any] = Field(default_factory=dict)


class ActivityBatchRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    device: ActivityDeviceInfo = Field(default_factory=ActivityDeviceInfo)
    events: List[ActivityEventIn] = Field(..., max_length=500)


class ActivityBatchResponse(BaseModel):
    accepted: int
    duplicates: int


class ActivityLinkRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)


class ActivityLinkResponse(BaseModel):
    linked: int


class ActivityLogUser(BaseModel):
    id: str
    full_name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    user_type: Optional[str] = None


class ActivityLogResponse(BaseModel):
    event_id: str
    name: str
    category: str
    client_ts: datetime
    received_at: datetime
    device_id: str
    session_id: str
    seq: int
    screen: Optional[str] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None
    user_type: Optional[str] = None
    pre_login: bool = False
    linked_at: Optional[datetime] = None
    props: Dict[str, Any] = Field(default_factory=dict)
    app_variant: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None
    ip: Optional[str] = None
    user: Optional[ActivityLogUser] = None


class ActivityLogListResponse(BaseModel):
    items: List[ActivityLogResponse]
    total: int


class ActivityDeviceResponse(BaseModel):
    device_id: str
    info: Dict[str, Any] = Field(default_factory=dict)
    user_ids: List[str] = Field(default_factory=list)
    last_user_id: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
