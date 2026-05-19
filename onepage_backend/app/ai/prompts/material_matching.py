SYSTEM_PROMPT = "你是一个素材匹配助手，根据风格和情绪推荐合适的贴纸、背景和装饰元素。"

USER_TEMPLATE = """请根据以下信息推荐素材关键词：

风格：{style}
情绪：{emotion}
场景：{scene}
天气：{weather}

请为以下每种素材类型输出 3-5 个标签关键词：
- stickers
- backgrounds
- decorations
- borders
- tapes

以 JSON 格式输出。"""
