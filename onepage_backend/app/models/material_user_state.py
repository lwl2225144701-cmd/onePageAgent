import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, UUIDMixin


class MaterialUserState(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "material_user_states"
    __table_args__ = (UniqueConstraint("material_id", "user_id", name="uq_material_user_state_material_user"),)

    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, server_default=None)
    favorited_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, server_default=None)

    def mark_used(self) -> None:
        self.last_used_at = func.now()

    def set_favorite(self, value: bool) -> None:
        self.is_favorite = value
        self.favorited_at = func.now() if value else None
