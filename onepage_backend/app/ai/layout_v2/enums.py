from enum import StrEnum


class MaterialRole(StrEnum):
    BACKGROUND = "background"
    FOCAL_STICKER = "focal_sticker"
    SUPPORTING_STICKER = "supporting_sticker"
    TAPE = "tape"
    FRAME = "frame"
    DECORATION = "decoration"
    NONE = "none"


MATERIAL_ROLES = tuple(role.value for role in MaterialRole if role is not MaterialRole.NONE)
