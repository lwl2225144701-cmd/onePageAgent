"""Rebuild the builtin materials library from the local SVG catalog."""
import asyncio

from scripts.ingest_builtin_materials import seed_builtin_materials


async def seed():
    await seed_builtin_materials(reset_existing=True)


if __name__ == "__main__":
    asyncio.run(seed())
