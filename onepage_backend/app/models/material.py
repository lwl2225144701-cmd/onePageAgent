from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Material(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "materials"

    material_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    style_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    emotion_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scene_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    meta_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
