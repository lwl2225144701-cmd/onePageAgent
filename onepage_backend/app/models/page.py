import uuid

from sqlalchemy import Date, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Page(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pages"

    journal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mood: Mapped[str | None] = mapped_column(String(50), nullable=True)
    page_date: Mapped[str | None] = mapped_column(Date, nullable=True)

    journal = relationship("Journal", back_populates="pages")
    elements = relationship("Element", back_populates="page", lazy="selectin", cascade="all, delete-orphan")
