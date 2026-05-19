from fastapi import APIRouter

from app.api.v1 import (
    uploads,
    ai_tasks,
    journals,
    pages,
    materials,
    weather,
    preferences,
    export,
)

api_router = APIRouter()
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(ai_tasks.router, prefix="/ai/tasks", tags=["AI Tasks"])
api_router.include_router(journals.router, prefix="/journals", tags=["Journals"])
api_router.include_router(pages.router, prefix="/pages", tags=["Pages"])
api_router.include_router(materials.router, prefix="/materials", tags=["Materials"])
api_router.include_router(weather.router, prefix="/weather", tags=["Weather"])
api_router.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])
