import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Element(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "elements"

    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    props_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    z_index: Mapped[int] = mapped_column(Integer, default=0)

    page = relationship("Page", back_populates="elements")
