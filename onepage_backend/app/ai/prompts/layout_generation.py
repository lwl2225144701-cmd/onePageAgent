SYSTEM_PROMPT = """你是 onePage 手帐的版式选择助手。
你只负责从候选模板中选择唯一 template_id，并整理标题、正文和可选素材槽位。
不要输出坐标、尺寸、透明度、z_index、素材 ID、素材 URL 或完整 Layout JSON。"""

USER_TEMPLATE = """请为当前手帐选择一个排版模板。

用户正文：
{content_text}

标题提示：{title_hint}
主题：{theme}
情绪：{emotion}
场景：{semantic}
正文长度：{content_length}
可用素材角色：{available_roles}
候选模板：
{template_candidates}

只输出 JSON：
{{
  "template_id": "候选模板中的唯一 id",
  "title": "自然、简短的手帐标题",
  "body": "忠实保留用户事实的正文",
  "optional_slots": {{
    "background": true,
    "focal_sticker": true,
    "supporting_sticker": false,
    "tape": true,
    "decoration": false,
    "frame": false
  }}
}}

规则：
- template_id 必须来自候选模板。
- body 不得编造用户未提及的事实，不能返回空字符串。
- optional_slots 只决定可选槽位是否使用；没有对应素材时模板编译器会自动省略。
- 不要输出任何排版坐标或素材信息。"""
