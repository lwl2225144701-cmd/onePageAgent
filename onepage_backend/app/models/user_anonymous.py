from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserAnonymous(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users_anonymous"

    anonymous_user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    last_active_at: Mapped[str] = mapped_column(String(128), nullable=True)
