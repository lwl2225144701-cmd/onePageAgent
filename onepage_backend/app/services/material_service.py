from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material


class MaterialService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_materials(
        self,
        material_type: str | None = None,
        style: str | None = None,
        emotion: str | None = None,
        scene: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Material], int]:
        base_q = select(Material)
        if material_type:
            base_q = base_q.where(Material.material_type == material_type)

        # For JSON array filtering, fetch and filter in Python (MVP material count is small)
        all_materials = (await self.db.execute(base_q)).scalars().all()

        filtered = []
        for m in all_materials:
            if style and (not m.style_tags or style not in m.style_tags):
                continue
            if emotion and (not m.emotion_tags or emotion not in m.emotion_tags):
                continue
            if scene and (not m.scene_tags or scene not in m.scene_tags):
                continue
            filtered.append(m)

        total = len(filtered)
        start = (page - 1) * size
        materials = filtered[start:start + size]
        return materials, total

    async def recommend(
        self,
        style: str | None = None,
        emotion: str | None = None,
        scene: str | None = None,
        weather: str | None = None,
    ) -> list[dict]:
        q = select(Material)
        all_materials = (await self.db.execute(q)).scalars().all()

        scored = []
        for m in all_materials:
            score = 0
            if emotion and m.emotion_tags and emotion in m.emotion_tags:
                score += 3
            if scene and m.scene_tags and scene in m.scene_tags:
                score += 2
            if style and m.style_tags and style in m.style_tags:
                score += 1
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)

        groups: dict[str, list] = {}
        for _, m in scored:
            if m.material_type not in groups:
                groups[m.material_type] = []
            if len(groups[m.material_type]) < 6:
                groups[m.material_type].append(m)

        return [{"material_type": t, "items": items} for t, items in groups.items()]
