from __future__ import annotations

import json

from app.ai.layout_v2.schemas import LayoutPlan, VisualBrief


SYSTEM_PROMPT = """你是 onePage 手帐的方案选择助手。
你只能从后端提供的合法完整方案中选择一个 template_id，并给出简短自然的标题。
不要输出正文、素材、角色、坐标、尺寸、透明度、optional_slots 或 z_index。"""


def build_plan_selection_prompt(brief: VisualBrief, plans: list[LayoutPlan]) -> str:
    candidates = [
        {
            "template_id": plan.template_id,
            "layout_type": plan.template_id.split("_")[0],
            "score": plan.score,
            "roles": sorted(plan.materials),
        }
        for plan in plans
    ]
    return (
        "从候选完整方案中选择最适合当前记录的一项。\n"
        f"视觉简报：{json.dumps(brief.model_dump(mode='json'), ensure_ascii=False)}\n"
        f"候选方案：{json.dumps(candidates, ensure_ascii=False)}\n"
        '只输出 JSON：{"template_id":"候选 ID","title":"不超过 20 个汉字的标题"}'
    )
