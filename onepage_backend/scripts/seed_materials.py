"""Seed the materials table with built-in assets."""
import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.material import Material

SEED_MATERIALS = [
    # Stickers - Happy / Warm
    {"material_type": "sticker", "style_tags": ["healing", "warm"], "emotion_tags": ["happy", "calm"],
     "scene_tags": ["daily", "home"], "file_url": "/materials/stickers/sunny_cat.png", "meta_info": {"name": "Sunny Cat"}},
    {"material_type": "sticker", "style_tags": ["cute", "warm"], "emotion_tags": ["happy", "excited"],
     "scene_tags": ["daily", "party"], "file_url": "/materials/stickers/happy_star.png", "meta_info": {"name": "Happy Star"}},
    {"material_type": "sticker", "style_tags": ["minimal", "elegant"], "emotion_tags": ["calm", "neutral"],
     "scene_tags": ["daily", "work"], "file_url": "/materials/stickers/botanical_line.png", "meta_info": {"name": "Botanical Line"}},

    # Stickers - Sad / Calm
    {"material_type": "sticker", "style_tags": ["healing", "soft"], "emotion_tags": ["sad", "calm"],
     "scene_tags": ["home", "rain"], "file_url": "/materials/stickers/gentle_cloud.png", "meta_info": {"name": "Gentle Cloud"}},
    {"material_type": "sticker", "style_tags": ["minimal", "cool"], "emotion_tags": ["calm", "neutral"],
     "scene_tags": ["rain", "night"], "file_url": "/materials/stickers/rain_drop.png", "meta_info": {"name": "Rain Drop"}},

    # Stickers - Travel / Adventure
    {"material_type": "sticker", "style_tags": ["vintage", "warm"], "emotion_tags": ["excited", "happy"],
     "scene_tags": ["travel", "outdoor"], "file_url": "/materials/stickers/travel_ticket.png", "meta_info": {"name": "Travel Ticket"}},
    {"material_type": "sticker", "style_tags": ["vintage", "earthy"], "emotion_tags": ["excited", "calm"],
     "scene_tags": ["travel", "outdoor"], "file_url": "/materials/stickers/map_pin.png", "meta_info": {"name": "Map Pin"}},
    {"material_type": "sticker", "style_tags": ["cute", "warm"], "emotion_tags": ["happy"],
     "scene_tags": ["travel", "food"], "file_url": "/materials/stickers/coffee_cup.png", "meta_info": {"name": "Coffee Cup"}},

    # Decorations
    {"material_type": "decoration", "style_tags": ["healing", "soft"], "emotion_tags": ["calm", "happy"],
     "scene_tags": ["daily"], "file_url": "/materials/decorations/floral_frame.png", "meta_info": {"name": "Floral Frame"}},
    {"material_type": "decoration", "style_tags": ["minimal", "elegant"], "emotion_tags": ["neutral", "calm"],
     "scene_tags": ["work", "daily"], "file_url": "/materials/decorations/line_divider.png", "meta_info": {"name": "Line Divider"}},
    {"material_type": "decoration", "style_tags": ["vintage", "warm"], "emotion_tags": ["excited", "happy"],
     "scene_tags": ["travel", "party"], "file_url": "/materials/decorations/washi_tape.png", "meta_info": {"name": "Washi Tape"}},

    # Backgrounds
    {"material_type": "background", "style_tags": ["healing", "soft"], "emotion_tags": ["calm", "happy", "neutral"],
     "scene_tags": ["daily"], "file_url": "/materials/backgrounds/cream_paper.png", "meta_info": {"name": "Cream Paper"}},
    {"material_type": "background", "style_tags": ["vintage", "earthy"], "emotion_tags": ["calm", "sad"],
     "scene_tags": ["travel", "coffee"], "file_url": "/materials/backgrounds/kraft_paper.png", "meta_info": {"name": "Kraft Paper"}},
    {"material_type": "background", "style_tags": ["cool", "minimal"], "emotion_tags": ["calm", "neutral"],
     "scene_tags": ["rain", "night"], "file_url": "/materials/backgrounds/misty_blue.png", "meta_info": {"name": "Misty Blue"}},
    {"material_type": "background", "style_tags": ["warm", "cute"], "emotion_tags": ["happy", "excited"],
     "scene_tags": ["party", "daily"], "file_url": "/materials/backgrounds/pink_bloom.png", "meta_info": {"name": "Pink Bloom"}},

    # Borders
    {"material_type": "border", "style_tags": ["healing", "soft"], "emotion_tags": ["calm", "happy"],
     "scene_tags": ["daily"], "file_url": "/materials/borders/floral_wreath.png", "meta_info": {"name": "Floral Wreath"}},
    {"material_type": "border", "style_tags": ["minimal", "elegant"], "emotion_tags": ["neutral"],
     "scene_tags": ["work", "daily"], "file_url": "/materials/borders/simple_line.png", "meta_info": {"name": "Simple Line"}},

    # Tapes
    {"material_type": "tape", "style_tags": ["healing", "cute"], "emotion_tags": ["happy", "calm"],
     "scene_tags": ["daily", "home"], "file_url": "/materials/tapes/pastel_washi.png", "meta_info": {"name": "Pastel Washi"}},
    {"material_type": "tape", "style_tags": ["vintage", "earthy"], "emotion_tags": ["calm", "excited"],
     "scene_tags": ["travel", "coffee"], "file_url": "/materials/tapes/vintage_tape.png", "meta_info": {"name": "Vintage Tape"}},
]


async def seed():
    async with async_session_factory() as session:
        result = await session.execute(select(Material).limit(1))
        if result.scalar_one_or_none():
            print("Materials already seeded, skipping.")
            return

        for item in SEED_MATERIALS:
            material = Material(
                material_type=item["material_type"],
                style_tags=item["style_tags"],
                emotion_tags=item["emotion_tags"],
                scene_tags=item["scene_tags"],
                file_url=item["file_url"],
                meta_info=item["meta_info"],
            )
            session.add(material)

        await session.commit()
        print(f"Seeded {len(SEED_MATERIALS)} materials.")


if __name__ == "__main__":
    asyncio.run(seed())
