from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UnifiedResponse(BaseModel, Generic[T]):
    success: bool = True
    error_code: str | None = None
    message: str | None = None
    data: T | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    data: dict | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PaginationMeta(BaseModel):
    page: int
    size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: list[T]
    pagination: PaginationMeta
