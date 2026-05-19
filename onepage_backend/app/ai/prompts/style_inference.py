SYSTEM_PROMPT = "你是一个专业的手账排版设计师，擅长根据内容、情绪和场景推荐视觉风格。"

USER_TEMPLATE = """请根据以下信息推荐手账页的视觉风格：

内容分析：{content_analysis}
情感分析：{sentiment}
天气：{weather}
用户偏好：{user_preferences}

请输出：
- theme: 主题风格（healing/warm/vintage/minimal/cute/cool/elegant）
- font: 推荐字体风格（handwriting/serif/sans-serif/brush）
- color_palette: 3-5 个推荐颜色（hex 格式）
- layout_style: 排版风格（minimal/dense/collage/diary）

权重参考：
- 内容语义 40%
- 情绪倾向 30%
- 天气因素 10%
- 用户偏好 20%

以 JSON 格式输出。"""
