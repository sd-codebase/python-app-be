from pydantic import BaseModel
from typing import List
from datetime import datetime


class GlobalNotification(BaseModel):
    id: str
    api_version: str
    messages: List[str]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
