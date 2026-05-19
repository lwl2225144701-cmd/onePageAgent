from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference import UserPreference

DEFAULT_PREFS = {
    "style_preferences": {"theme": "healing", "layout_style": "minimal"},
    "font_preferences": {"font": "handwriting", "size": "medium"},
    "color_preferences": {"palette": ["#FAF6F0", "#E8B4B8", "#C4A882"]},
    "behavior_stats": {},
}


class PreferenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: str) -> UserPreference:
        q = select(UserPreference).where(UserPreference.user_id == user_id)
        result = (await self.db.execute(q)).scalar_one_or_none()
        if not result:
            result = UserPreference(user_id=user_id, **DEFAULT_PREFS)
            self.db.add(result)
            await self.db.flush()
            await self.db.refresh(result)
        return result

    async def update(self, user_id: str, data: dict) -> UserPreference:
        prefs = await self.get_or_create(user_id)
        for field in ["style_preferences", "font_preferences", "color_preferences", "behavior_stats"]:
            if field in data and data[field] is not None:
                setattr(prefs, field, data[field])
        await self.db.flush()
        await self.db.refresh(prefs)
        return prefs
