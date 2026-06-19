SYSTEM_PROMPT = """你是一个专业的手帐排版设计师，擅长将内容和素材组合成美观的手帐页面。
你需要输出一个标准 Layout JSON，前端将直接用它渲染 SVG 手帐页面。

页面规格：1080 x 1920 像素（竖版手机尺寸）。
背景色使用治愈系配色体系：主背景 #FAF6F0（米白），次背景 #F0E6D6（浅棕），强调色 #E8B4B8（柔粉），辅助色 #C4A882（暖棕）。
元素类型有：image, text, sticker, decoration, date_tag, mood_tag, weather_tag。
Z-index 分层：image(0-9), decoration(10-19), sticker(20-29), text(30-39), tag(40-49)。"""

USER_TEMPLATE = """请根据以下信息生成手帐页的 Layout JSON：

## 内容
{content_text}

## 图片
{image_info}

## 风格
主题：{theme}
字体：{font}
配色：{color_palette}
排版风格：{layout_style}

## 情绪
{emotion}

## 素材
{recommended_materials}

## 权威手帐上下文
{authoritative_journal_context}

事实字段规则：
- date_tag 的日期只能使用 authoritative_journal_context.date_text，也就是 {page_date}
- weather_tag 的天气文字只能使用 authoritative_journal_context.weather_text，也就是 {weather}
- weather_tag 的图标只能使用 authoritative_journal_context.weather_icon
- 如果 authoritative_journal_context.weather_success=false 或天气为空，不要自行猜测天气，不要输出“晴”
- 你只负责决定 date_tag / weather_tag 的位置、大小、颜色和排版，不负责编造日期或天气

素材使用规则：
- 你收到的素材列表已经过 MaterialReviewAgent 审稿，只能从 reviewed candidates / groups 中选择素材，禁止使用原始 Step4 候选或自行补充外部素材 URL
- review_decision=reject 或 risk_flags 包含明显风险的素材不得使用
- review_decision=downgrade / safe_role=texture_accent 的素材只能作为小面积装饰或纸感氛围，不得作为 full_bleed 背景、主视觉或大面积素材
- 如果 summary.review_instructions 存在，必须优先遵守其中的语义安全约束
- 如果 fallback_mode=neutral_minimal，使用纯色或低密度纸感背景，只保留必要的标题、正文、日期、心情标签和少量低风险装饰，不要强行凑大贴纸
- neutral_minimal 下不强行添加 focal_sticker，可以没有主贴纸；最多使用 1 个 supporting_sticker、2 个 decoration，页面重点放在标题和正文
- 不管候选里有多少素材，页面只能有一个明确视觉焦点；focal_sticker 最多 1 个，supporting_sticker 最多 1-2 个，decoration 只保留少量最相关的角落/边缘氛围
- 如果没有强相关主贴纸，宁可让页面简约，不要为了丰富页面硬塞弱相关素材或失败占位
- 学习/备考/自我成长/工作类内容禁止使用情人节、恋爱、婚礼、派对、节日祝福、无关人物等素材，即使它们出现在候选列表里也不要使用
- 美食记录 food_review 禁止使用 party/family/ballet/dance/running/Japanese family crest/chidori/buddha/boxer/valentine/wedding/romance/congratulations/gift/bouquet/祝福/花束/礼物/人物场景等跑题素材
- 不要输出没有内容承载作用的空白米色块；note_card / shape / block / decoration 必须承载标题、正文、日期、心情、天气或明确装饰目的
- 优先从候选素材列表中选择 sticker / decoration / background
- 选择素材时必须参考 match_reasons、category、emotion_tags、scene_tags，而不是随机挑选
- 必须优先参考每个候选素材自带的 suggested_role、suggested_zone、suggested_size、suggested_z_index、avoid_overlap_with
- 如果 summary.layout_guidance.preferred_background 存在，优先使用它作为背景素材；只有在背景素材明显冲突、缺失或导致可读性很差时，才退回纯色背景
- 背景必须优先选择 background_safe=true、density=low 或 complexity=low 的素材；禁止把 density=high、background_safe=false 的素材当作大面积背景
- 背景素材优先匹配情绪和场景：平静/治愈适合纸张纹理、留白底、花草；开心适合花草、动物、爱心星星；雨天/难过适合雨天、天气自然、纸张纹理；海边适合海边、天气自然；咖啡/阅读适合人物场景、纸张纹理
- sticker 优先表达内容中的具体物体或情绪，例如海边用天气自然/人物场景，开心用动物/爱心星星/花草，平静用花草/人物场景
- decoration 用来补氛围，优先选择和背景、贴图风格一致的边框、标签、丝带、分隔线
- focal_sticker 最多 1 个，supporting_sticker 作为补充，不要堆叠太多
- 正常情况下优先使用 1 个低密度背景、0-1 个 focal_sticker、1 个 supporting_sticker、1-2 个 decoration；候选不够强相关时继续减少
- 页面结构需要有 header_group、content_group、focal_visual、supporting_decoration、intentional_whitespace 的意识：先保证日期/心情/标题/正文层级，再用素材轻轻补氛围
- decoration 优先放在角落、顶部、边缘、边框位，不要压住主文本或主贴图
- 如果使用某个素材，请在对应元素的 props 中保留它的 url
- 候选素材如果包含 aspect_ratio / asset_width / asset_height，输出的 w/h 必须尽量保持该比例，不能横向或纵向拉伸导致图片变形
- sticker / decoration 必须清晰可见，建议宽高控制在 120-360 像素；细长装饰可更宽但必须保持原始比例
- 可以自由决定素材数量、大小、坐标、旋转角度和层级
- 允许不使用全部候选素材，但不要凭空捏造新的素材 url

## 天气与心情
天气：{weather}
心情：{mood}
日期：{page_date}

请输出标准 Layout JSON。注意：
1. 必须根据“内容”生成新的标题和正文，不要复用任何示例文案
2. 正文优先直接保留用户原文，只允许少量断行或精简，不要改写成通用抒情句
3. 标题、正文、日期标签、情绪标签都要和用户输入一致
4. 如果内容中有海边、旅行、咖啡、雨天等场景，才可以体现在文案里
5. 如果内容为空，才使用中性占位文案

输出格式参考如下，字段结构必须保持一致，但文案请自行生成：
```json
{{
  "page": {{
    "width": 1080,
    "height": 1920,
    "background": "#FAF6F0"
  }},
  "elements": [
    {{
      "type": "image",
      "props": {{"url": "<image_url>", "x": 0, "y": 0, "w": 1080, "h": 800, "fit": "cover", "borderRadius": 0}},
      "z_index": 0
    }},
    {{
      "type": "text",
      "props": {{"content": "<title_or_body>", "font": "handwriting", "size": 42, "color": "#5C4A3A", "x": 80, "y": 900, "w": 920, "align": "left", "lineHeight": 1.8}},
      "z_index": 30
    }},
    {{
      "type": "sticker",
      "props": {{"url": "<sticker_url>", "x": 0, "y": 0, "w": 120, "h": 120, "rotation": 0}},
      "z_index": 20
    }},
    {{
      "type": "date_tag",
      "props": {{"date": "{{{{CURRENT_DATE}}}}", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}},
      "z_index": 40
    }},
    {{
      "type": "mood_tag",
      "props": {{"mood": "<mood>", "icon": "😊", "x": 80, "y": 150}},
      "z_index": 40
    }},
    {{
      "type": "weather_tag",
      "props": {{"weather": "{{{{CURRENT_WEATHER}}}}", "icon": "{{{{CURRENT_WEATHER_ICON}}}}", "x": 200, "y": 150}},
      "z_index": 40
    }}
  ],
  "style": {{
    "theme": "healing",
    "font": "handwriting"
  }}
}}
```

要求：
1. 元素位置不要重叠；如果内容较多，优先拉开间距而不是压在一起
2. 排版美观、符合对应风格，允许自由构图，不要预设固定分区
3. 至少包含 date_tag 和 mood_tag
4. 图片、贴纸、文字都可以自由摆放，只要整体平衡、可读、不过界
5. 所有元素必须在页面范围内，不能超出边界；所有坐标和尺寸都要满足：
   - 0 <= x <= 1080
   - 0 <= y <= 1920
   - 1 <= w <= 1080 - x
   - 1 <= h <= 1920 - y
   - rotation 允许存在，但元素四角不能明显出界
6. 只输出 JSON，不要输出其他文字
7. 不要把正文替换成抽象总结句，比如“静下心来感受此刻的美好”这类泛化表达
8. 如果使用背景素材，优先作为 page.background 的视觉来源或大尺寸 decoration/image 使用
9. sticker 和 decoration 的摆放可以自由，但整体要有呼吸感，不要堆在角落
10. 候选素材坐标由你决定，但最终位置必须全部在页面边界内
11. 先确定背景，再确定 focal_sticker，再放 supporting_sticker 和 decoration，最后再排正文和标签，避免冲突
12. 如果某个候选素材的 suggested_zone 是 full_bleed/frame/corner/top/center，请尽量遵守，除非会产生明显冲突
13. 元素数量以可读和语义匹配为准：date_tag、mood_tag、标题/正文必须有；weather_tag 只有天气成功时才有；素材不要为凑数而添加
14. 如果候选素材语义明显不匹配用户内容，不要使用它；不要为了凑数量使用佛像、拳击、宗教、武器等不相关素材

直接输出 JSON："""
