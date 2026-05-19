SYSTEM_PROMPT = "你是一个专业的情感分析助手，擅长从文字和图片描述中识别细腻的情感层次。"

USER_TEMPLATE = """请分析以下内容的情感倾向：

文本内容：{content_text}
图片描述：{image_descriptions}
用户选择的心情：{user_mood}

请输出：
- primary_emotion: 主要情绪（happy/calm/excited/sad/nostalgic/neutral）
- secondary_emotion: 次要情绪
- confidence: 置信度（0-1）
- keywords: 情绪关键词列表

以 JSON 格式输出。"""
