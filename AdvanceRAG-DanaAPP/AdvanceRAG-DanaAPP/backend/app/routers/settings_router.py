from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, LOCAL_WORKSPACE_ID
from app.models import AppSettings
from app.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_or_create(db: AsyncSession, workspace_id: str = LOCAL_WORKSPACE_ID) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.workspace_id == workspace_id))
    s = result.scalar_one_or_none()
    if not s:
        s = AppSettings(workspace_id=workspace_id)
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await _get_or_create(db)


@router.patch("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_or_create(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.commit()
    await db.refresh(s)
    return s
