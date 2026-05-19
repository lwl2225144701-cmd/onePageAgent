from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    style_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    font_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    color_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    behavior_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
