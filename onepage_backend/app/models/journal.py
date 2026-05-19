from sqlalchemy import Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Journal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "journals"

    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    pages = relationship("Page", back_populates="journal", lazy="selectin", cascade="all, delete-orphan")
