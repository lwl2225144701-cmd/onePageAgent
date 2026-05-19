# 有一页 OnePage - 后端 MVP 实现逻辑拆解文档

## 文档信息

| 项目 | 内容 |
|---|---|
| 项目名称 | 有一页 OnePage |
| 文档类型 | 后端 MVP 实现逻辑 |
| 技术架构 | Python 技术栈 + 高并发异步架构 |
| 后端框架 | FastAPI |
| 异步任务 | Celery |
| 队列 | Redis Queue / Celery Queue |
| 数据库 | PostgreSQL |
| 对象存储 | MinIO / OSS |
| AI模型 | SenseVoiceSmall / Qwen-VL / DeepSeek / Qwen |
| 部署 | Docker Compose，后续可扩展 Kubernetes |

---

# 一、后端 MVP 核心目标

MVP 后端不是做完整平台，而是先支撑核心闭环：

```text
用户上传素材 / 输入文本
→ 创建 AI 生成任务
→ 异步处理语音 / 图片 / 文本
→ 调用模型生成 Layout JSON
→ 前端渲染 SVG 手账页
→ 保存手账页
→ 支持导出图片
```

后端 MVP 的核心价值：

```text
稳定接入 AI 能力 + 异步任务调度 + 数据持久化 + 资源管理
```

---

# 二、后端 MVP 模块总览

| 模块 | 是否 MVP 必须 | 技术选型 | 复杂度 |
|---|---|---|---|
| API 网关模块 | 是 | Nginx / FastAPI Router | 中 |
| 用户会话模块 | 是 | 匿名 user_id / session_id | 低 |
| 上传服务模块 | 是 | FastAPI UploadFile + MinIO/OSS | 中 |
| 天气服务模块 | 是 | 第三方天气 API + Redis Cache | 低 |
| 偏好服务模块 | 是 | PostgreSQL / Redis | 中 |
| AI任务模块 | 是 | Celery + Redis | 高 |
| AI编排模块 | 是 | Python Service Layer | 极高 |
| 模型网关模块 | 是 | LLM Gateway | 高 |
| 手账本服务模块 | 是 | PostgreSQL | 中高 |
| 素材服务模块 | 是 | PostgreSQL + MinIO/OSS | 中 |
| 导出任务模块 | MVP Lite | Celery + Headless Renderer | 中高 |
| SSE推送模块 | 是 | FastAPI SSE | 中 |
| 日志监控模块 | 是 | logging + Prometheus | 中 |

---

# 三、后端整体实现链路

## 3.1 用户生成一页手账的完整后端链路

```text
1. 前端提交文本、图片、心情、天气、语音
2. 后端创建生成任务 task_id
3. 保存原始输入数据
4. 将任务写入 Celery 队列
5. 前端通过 SSE 监听任务进度
6. Worker 按步骤执行 AI 编排
7. 调用语音 / 图片 / 文本 / LLM 模型
8. 生成标准 Layout JSON
9. 保存 Page 与 Element 数据
10. 返回生成结果
11. 前端渲染可编辑 SVG
```

---

# 四、API 网关与应用服务层

## 4.1 模块职责

负责所有 HTTP 请求入口。

### 技术选型

```text
Nginx / API Gateway
FastAPI
Uvicorn
Pydantic
```

---

## 4.2 MVP 需要的 API 分类

| API 分类 | 说明 |
|---|---|
| 上传 API | 图片、语音上传 |
| AI任务 API | 创建生成任务、查询任务状态 |
| 手账本 API | 创建、查询、删除手账本 |
| 手账页 API | 保存、查询、删除页面 |
| 素材 API | 查询贴纸、背景、字体 |
| 天气 API | 获取当前天气 |
| 偏好 API | 保存用户偏好 |
| 导出 API | 创建导出任务 |

---

# 五、用户会话模块

## 5.1 MVP 不做账号体系

MVP 阶段建议不做完整登录注册。

采用：

```text
anonymous_user_id + session_id
```

---

## 5.2 生成逻辑

用户首次访问时：

```text
前端生成 anonymous_user_id
后端接受并绑定资源
```

---

## 5.3 数据绑定关系

```text
anonymous_user_id
 ├── journals
 ├── pages
 ├── uploads
 ├── preferences
 └── ai_tasks
```

---

# 六、上传服务模块

## 6.1 模块职责

负责接收和管理用户素材。

---

## 6.2 上传类型

| 类型 | 用途 | 存储位置 |
|---|---|---|
| image | 用户上传照片 | MinIO / OSS |
| audio | 语音输入 | MinIO / 临时存储 |
| material | 内置素材 | MinIO / OSS |

---

## 6.3 图片上传流程

```text
1. 前端上传图片
2. FastAPI 接收 UploadFile
3. 校验文件类型 / 大小
4. 生成 file_id
5. 上传到 MinIO / OSS
6. 写入 upload_assets 表
7. 返回 file_url / file_id
```

---

## 6.4 音频上传流程

```text
1. 前端录音完成
2. 上传音频文件
3. 后端保存临时音频
4. 创建 voice_queue 任务
5. Worker 调用 SenseVoiceSmall / ASR
6. 返回文本和情绪标签
```

---

# 七、天气服务模块

## 7.1 模块职责

根据前端定位结果获取天气。

---

## 7.2 实现逻辑

```text
1. 前端传 latitude / longitude
2. 后端查询 Redis weather_cache
3. 命中缓存，直接返回
4. 未命中，调用第三方天气 API
5. 写入 Redis，TTL 24 小时
6. 返回天气结果
```

---

## 7.3 fallback

如果天气 API 失败：

```json
{
  "weather": "晴",
  "temperature": null,
  "location": "未知"
}
```

---

# 八、偏好服务模块

## 8.1 MVP 只做轻量偏好

不做复杂推荐系统。

MVP 只保存：

- 用户常用风格
- 用户常用字体
- 用户常用颜色
- 用户编辑行为摘要

---

## 8.2 数据来源

```text
用户生成手账
用户编辑字体
用户替换贴纸
用户导出页面
```

---

## 8.3 后端用途

偏好数据参与 AI 风格推断：

```text
内容语义 40%
情绪倾向 30%
天气因素 10%
用户偏好 20%
```

---

# 九、AI任务模块

## 9.1 模块职责

负责所有长耗时 AI 任务异步化。

---

## 9.2 技术选型

```text
Celery
Redis Broker
Redis Result Backend
```

---

## 9.3 队列拆分

| 队列 | 职责 |
|---|---|
| voice_queue | 语音识别 / 情绪识别 |
| image_queue | 图片理解 |
| llm_queue | 文本理解 / 风格推断 / 排版生成 |
| export_queue | 图片 / PDF 导出 |

---

## 9.4 为什么要拆队列

原因：

```text
不同任务耗时不同
不同模型资源不同
方便限流
方便扩容
避免大任务阻塞小任务
```

---

# 十、AI 编排模块

## 10.1 模块职责

这是后端最核心模块。

负责把用户输入变成标准 Layout JSON。

---

## 10.2 AI 编排主流程

```text
输入内容
 ├── 文本
 ├── 图片
 ├── 语音
 ├── 心情
 ├── 天气
 └── 用户偏好

↓

AI 编排链路
 ├── Step 1：语音识别
 ├── Step 2：语音情绪识别
 ├── Step 3：图片理解
 ├── Step 4：文本内容理解
 ├── Step 5：综合情绪分析
 ├── Step 6：风格推断
 ├── Step 7：素材推荐
 ├── Step 8：排版生成
 ├── Step 9：JSON 修复
 └── Step 10：兜底校验

↓

输出 Layout JSON
```

---

## 10.3 MVP 可简化链路

MVP 第一版建议简化为：

```text
Step 1：内容理解
Step 2：情感分析
Step 3：风格推断
Step 4：素材匹配
Step 5：排版生成
Step 6：JSON 校验与修复
```

---

# 十一、模型服务层

## 11.1 模型选型

按照当前技术架构：

| 模型 | 用途 |
|---|---|
| SenseVoiceSmall | 语音情绪识别 |
| Qwen-VL | 图片理解 |
| DeepSeek | 文本分析 / 推理 |
| Qwen | 通用文本生成 |
| LLM Gateway | 模型统一入口 |
| JSON修复与兜底 | 修复模型输出格式 |

---

## 11.2 LLM Gateway 职责

统一封装不同模型：

```text
调用参数
鉴权
超时
重试
限流
日志
fallback
```

---

## 11.3 模型调用优先级

### 图片理解

```text
Qwen-VL
```

### 文本理解

```text
DeepSeek / Qwen
```

### 排版生成

```text
Qwen / DeepSeek
```

### JSON 修复

```text
Qwen Lite / 本地规则修复
```

---

# 十二、Layout JSON 生成逻辑

## 12.1 后端输出标准

后端最终必须输出前端可直接渲染的数据：

```json
{
  "page": {
    "width": 1080,
    "height": 1920,
    "background": "#FAF6F0"
  },
  "elements": [],
  "style": {
    "theme": "healing",
    "font": "handwriting"
  }
}
```

---

## 12.2 元素类型

MVP 支持：

| 类型 | 说明 |
|---|---|
| image | 用户图片 |
| text | 文本内容 |
| sticker | 贴纸 |
| decoration | 装饰 |
| date_tag | 日期标签 |
| mood_tag | 心情标签 |
| weather_tag | 天气标签 |

---

## 12.3 兜底规则

如果 LLM 输出异常：

```text
1. 尝试 JSON 修复
2. 尝试字段补全
3. 尝试元素边界修正
4. 尝试 zIndex 修正
5. 如果仍失败，使用默认模板
```

---

# 十三、手账本服务模块

## 13.1 模块职责

负责 Journal / Page / Element 的持久化。

---

## 13.2 核心模型

```text
Journal
 └── Page
      └── Element
```

---

## 13.3 核心接口

| 接口 | 用途 |
|---|---|
| POST /journals | 创建手账本 |
| GET /journals | 查询手账本列表 |
| GET /journals/{id} | 查询手账本详情 |
| DELETE /journals/{id} | 删除手账本 |
| POST /pages | 保存手账页 |
| GET /pages/{id} | 查询页面详情 |
| PUT /pages/{id} | 更新页面 |
| DELETE /pages/{id} | 删除页面 |

---

# 十四、素材服务模块

## 14.1 模块职责

负责贴纸、背景、字体等素材查询。

---

## 14.2 素材分类

```text
materials
 ├── stickers
 ├── backgrounds
 ├── borders
 ├── decorations
 ├── tapes
 └── fonts
```

---

## 14.3 素材匹配逻辑

```text
输入：style + emotion + weather + scene
输出：推荐素材列表
```

MVP 可以先用规则匹配：

```text
开心 → 可爱 / 温暖贴纸
雨天 → 清新 / 蓝色系背景
旅行 → 票据 / 地图 / 胶带素材
咖啡 → 复古 / 文艺素材
```

---

# 十五、导出服务模块

## 15.1 MVP 建议

第一版导出主要放前端完成。

后端只保留导出任务接口。

---

## 15.2 后续服务端导出

如果后续要支持 PDF / 批量导出，需要：

```text
export_queue
Headless Chrome
SVG Render
PDF Render
ZIP打包
```

---

# 十六、SSE 推送服务

## 16.1 为什么用 SSE

MVP 阶段，AI生成进度是服务端单向推送。

SSE 比 WebSocket 更轻。

---

## 16.2 推送内容

```json
{
  "task_id": "xxx",
  "step": 3,
  "step_name": "风格推断",
  "status": "processing",
  "progress": 60
}
```

---

## 16.3 状态类型

| 状态 | 说明 |
|---|---|
| pending | 等待中 |
| processing | 处理中 |
| completed | 已完成 |
| failed | 失败 |
| timeout | 超时 |

---

# 十七、数据库设计 MVP 版

## 17.1 PostgreSQL 表

### users_anonymous

```text
id
anonymous_user_id
created_at
last_active_at
```

---

### journals

```text
id
user_id
name
cover_url
page_count
settings
created_at
updated_at
```

---

### pages

```text
id
journal_id
user_id
title
content_text
layout_json
thumbnail_url
weather
mood
page_date
created_at
updated_at
```

---

### elements

```text
id
page_id
element_type
props_json
z_index
created_at
updated_at
```

---

### upload_assets

```text
id
user_id
asset_type
file_url
file_name
file_size
mime_type
created_at
```

---

### ai_tasks

```text
id
task_id
user_id
status
progress
input_json
result_json
error_message
created_at
updated_at
```

---

### materials

```text
id
material_type
style_tags
emotion_tags
scene_tags
file_url
metadata
created_at
```

---

### user_preferences

```text
id
user_id
style_preferences
font_preferences
color_preferences
behavior_stats
created_at
updated_at
```

---

# 十八、Redis 使用场景

| Key | 用途 | TTL |
|---|---|---|
| task:{task_id}:status | AI任务状态 | 24h |
| weather:{lat}:{lng} | 天气缓存 | 24h |
| sse:{task_id} | SSE进度 | 1h |
| rate_limit:{user_id} | 限流 | 1min |
| celery_result:{task_id} | Celery结果 | 24h |

---

# 十九、后端接口清单 MVP

## 19.1 上传接口

```text
POST /api/uploads/image
POST /api/uploads/audio
```

---

## 19.2 AI任务接口

```text
POST /api/ai/tasks
GET /api/ai/tasks/{task_id}
GET /api/ai/tasks/{task_id}/events
```

---

## 19.3 手账本接口

```text
POST /api/journals
GET /api/journals
GET /api/journals/{journal_id}
DELETE /api/journals/{journal_id}
```

---

## 19.4 手账页接口

```text
POST /api/pages
GET /api/pages/{page_id}
PUT /api/pages/{page_id}
DELETE /api/pages/{page_id}
```

---

## 19.5 素材接口

```text
GET /api/materials
GET /api/materials/recommend
```

---

## 19.6 天气接口

```text
GET /api/weather
```

---

# 二十、后端 MVP 开发顺序

## 第一阶段：后端基础能力

```text
FastAPI项目初始化
PostgreSQL连接
Redis连接
MinIO连接
基础异常处理
统一响应结构
```

---

## 第二阶段：资源与数据

```text
上传服务
素材服务
手账本服务
手账页服务
```

---

## 第三阶段：AI任务系统

```text
Celery接入
任务创建
任务状态管理
SSE进度推送
```

---

## 第四阶段：AI编排链路

```text
内容理解
情感分析
风格推断
素材匹配
排版生成
JSON修复
```

---

## 第五阶段：稳定性增强

```text
限流
日志
监控
fallback
错误重试
Docker Compose部署
```

---

# 二十一、后端 MVP 工作量统计

| 模块 | 工作量 |
|---|---|
| FastAPI基础工程 | 2~3 天 |
| 数据库模型 | 2~3 天 |
| 上传服务 | 2~3 天 |
| MinIO/OSS接入 | 1~2 天 |
| 手账本服务 | 3~4 天 |
| 手账页服务 | 3~4 天 |
| 素材服务 | 2~3 天 |
| 天气服务 | 1 天 |
| Redis缓存 | 1~2 天 |
| Celery任务系统 | 3~5 天 |
| SSE推送 | 2~3 天 |
| AI Gateway | 4~6 天 |
| AI编排链路 | 7~12 天 |
| Layout JSON校验 | 3~5 天 |
| 日志监控 | 2~3 天 |
| Docker Compose | 1~2 天 |

---

## 总工作量

```text
39 ~ 63 人天
```

如果 AI Coding 辅助较强：

```text
25 ~ 40 人天
```

---

# 二十二、后端 MVP 最终结论

后端 MVP 最重要的不是 CRUD。

真正核心是：

```text
异步任务调度
+
AI模型编排
+
Layout JSON稳定输出
+
素材与手账数据管理
```

其中最难的是：

```text
AI 编排链路
Layout JSON 生成
JSON 修复与兜底
```

后端第一版必须保证：

```text
即使 AI 失败，也能输出一个可渲染的默认手账页。
```

这是整个 MVP 能不能稳定演示、稳定上线的关键。

