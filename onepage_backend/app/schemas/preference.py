from datetime import datetime

from pydantic import BaseModel


class UpdatePreferenceRequest(BaseModel):
    style_preferences: dict | None = None
    font_preferences: dict | None = None
    color_preferences: dict | None = None
    behavior_stats: dict | None = None


class UserPreferenceResponse(BaseModel):
    id: str
    user_id: str
    style_preferences: dict | None = None
    font_preferences: dict | None = None
    color_preferences: dict | None = None
    behavior_stats: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
