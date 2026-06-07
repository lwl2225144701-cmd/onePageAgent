from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.serializers import to_preference_response
from app.schemas.common import UnifiedResponse
from app.schemas.preference import UpdatePreferenceRequest, UserPreferenceResponse
from app.services.preference_service import PreferenceService

router = APIRouter()


@router.get("", response_model=UnifiedResponse[UserPreferenceResponse])
async def get_preferences(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PreferenceService(db)
    prefs = await svc.get_or_create(user_id)
    return UnifiedResponse(data=to_preference_response(prefs))


@router.put("", response_model=UnifiedResponse[UserPreferenceResponse])
async def update_preferences(
    body: UpdatePreferenceRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PreferenceService(db)
    prefs = await svc.update(user_id, body.model_dump(exclude_none=True))
    return UnifiedResponse(data=to_preference_response(prefs))
