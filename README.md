# 有一页 onepage

有一页 onepage 是一个 AI 手账应用原型：用户写下当天的内容、选择心情与素材后，系统会理解记录、匹配素材、生成手账版式，并支持进入编辑器继续调整、保存和导出。

项目由前端 `onepage_frontend` 与后端 `onepage_backend` 组成。前端提供奶油纸感、日系手账风的移动端体验；后端提供 AI 任务编排、素材库、手账本、页面、偏好、上传、导出等 API 能力。

## 主要功能

- 创作入口：文字输入、心情选择、天气/位置展示、AI 生成入口。
- AI 生成流程：内容理解、情绪分析、风格推断、素材匹配、版式生成、修复兜底。
- 手账编辑器：沉浸式编辑页、拖拽/缩放/选中、文字与贴纸替换、PNG/JPEG/PDF 导出。
- 我的手账本：多层原木书架风格，支持年份手账本与新增入口。
- 素材库：贴图、背景、拼贴元素三类素材，支持搜索、分类筛选、收藏、最近使用和上传。
- 我的页面：用户信息、手账统计、风格偏好、收藏/草稿/导出/设置入口。
- 后端服务：匿名用户、素材状态、MinIO 资源、SSE 任务进度、Celery worker 队列。

## 技术栈

### 前端

- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- Zustand
- Konva / react-konva
- lucide-react

### 后端

- FastAPI
- SQLAlchemy async
- PostgreSQL
- Redis
- Celery
- MinIO
- Pydantic Settings
- pytest

## 目录结构

```text
.
├── onepage_frontend/          # Next.js 前端应用
│   ├── src/api/               # 前端 API client
│   ├── src/modules/           # 页面与业务模块
│   │   ├── ai/                # AI 生成中页面
│   │   ├── create/            # 首页/创作输入页
│   │   ├── editor/            # 手账编辑器
│   │   ├── journal/           # 我的手账本
│   │   ├── materials/         # 素材库
│   │   └── profile/           # 我的页面
│   ├── src/stores/            # Zustand 状态
│   └── src/types/             # 后端响应类型
│
├── onepage_backend/           # FastAPI 后端服务
│   ├── app/api/v1/            # API 路由
│   ├── app/ai/                # AI pipeline、prompt、fallback
│   ├── app/core/              # DB/Redis/MinIO/日志/中间件
│   ├── app/models/            # SQLAlchemy 模型
│   ├── app/schemas/           # Pydantic schema
│   ├── app/services/          # 业务服务
│   ├── app/workers/           # Celery worker
│   ├── scripts/               # 初始化、导入、回填脚本
│   └── tests/                 # 后端测试
│
└── README.md
```

## 本地启动

### 1. 后端

后端默认通过 Docker Compose 启动 API 与多个 worker，并依赖外部 `infra_default` 网络中的 PostgreSQL、Redis、MinIO。

```bash
cd onepage_backend
make build
make up
```

初始化数据库与 MinIO bucket：

```bash
make init-infra
make migrate
```

导入/重建内置素材：

```bash
make seed
make rebuild-materials
```

查看日志：

```bash
make logs
```

后端 API 默认监听：

```text
http://127.0.0.1:8000
```

#### 使用本地虚拟环境启动

如果不通过 Docker Compose 启动后端，需要分别打开三个终端，并在每个终端中进入后端目录、激活虚拟环境。

终端 1：启动 FastAPI：

```bash
cd onepage_backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

终端 2：启动 AI 生成 Worker：

```bash
cd onepage_backend
source .venv/bin/activate
celery -A app.workers.celery_app worker -Q llm_queue --concurrency=1 --loglevel=info
```

终端 3：启动导出 Worker：

```bash
cd onepage_backend
source .venv/bin/activate
celery -A app.workers.celery_app worker -Q export_queue --concurrency=1 --loglevel=info
```

AI 视觉审稿默认使用阿里云百炼 OpenAI 兼容接口；未配置 Key 时会自动退回规则审稿，不会阻断生成链路。

```env
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_REVIEW_PROVIDER=dashscope
VISION_REVIEW_MODEL=qwen3-omni-flash
```

天气和地点上下文由 MCP 工具提供。MCP 服务、后端和连通性检查脚本默认都读取 `onepage_backend/.env`，所以高德 Key、MCP 监听地址和后端连接地址统一维护在这一份文件里。无有效地点时，后端会先尝试自动定位，再按 `DEFAULT_WEATHER_LOCATION` 降级；仍失败时只保留日期时间，不让模型编造天气。

```env
AMAP_WEB_SERVICE_KEY=
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_PATH=/mcp
AMAP_WEATHER_MCP_URL=http://127.0.0.1:8001/mcp
MCP_TOOL_TIMEOUT_SECONDS=10
DEFAULT_WEATHER_LOCATION=深圳
```

### 2. 前端

```bash
cd onepage_frontend
npm install
npm run dev
```

前端默认监听：

```text
http://127.0.0.1:3000
```

## 常用命令

### 前端

```bash
cd onepage_frontend
npm run dev
npm run build
npm run start
npm run audit:integration
```

### 后端

```bash
cd onepage_backend
make test
make lint
make migrate
make migration-create NAME="your migration name"
```

## 环境变量

运行时配置统一以 `onepage_backend/.env` 为主，默认模板维护在 `onepage_backend/.env.example`。后端 `app/config.py` 只负责声明 Pydantic Settings 类型、读取环境变量和做校验；默认值来自 `.env.example`，本地真实值由项目根 `.env` 或 `onepage_backend/.env` 覆盖。业务代码统一从 `app.config import settings` 获取最终配置。MCP 服务也会优先读取同一份 backend 配置。

前端的 `onepage_frontend/.env.example` 只保留 `NEXT_PUBLIC_API_BASE_URL`，这是 Next.js 浏览器端公开变量，不和后端密钥配置合并。`tsconfig`、`tailwind.config`、`next.config`、`pyproject.toml`、`docker-compose.yml` 属于构建/工具配置，不作为运行时密钥配置合并。

主要运行时配置项包括：

- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `DEEPSEEK_API_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `QWEN_API_URL`
- `QWEN_API_KEY`
- `DASHSCOPE_API_KEY`
- `VISION_REVIEW_MODEL`
- `AMAP_WEB_SERVICE_KEY`
- `AMAP_WEATHER_MCP_URL`
- `PUBLIC_API_BASE_URL`
- `MCP_TRANSPORT`
- `MCP_HOST`
- `MCP_PORT`
- `MCP_PATH`

如果不配置真实 AI Key，后端仍可通过 fallback layout 与本地演示逻辑支撑部分流程。

## 素材库标签设计

素材库当前采用三层结构：

1. 素材类型：`sticker`、`background`、`decoration`
2. 内容分类：例如花草、天气自然、纸张纹理、牛皮纸、边框、标签等
3. 风格/语义标签：例如线稿、手绘、插画、复古、可爱、极简等

前端搜索会匹配：

- `meta_info.category`
- `meta_info.display_name`
- `meta_info.tags`
- `style_tags`
- `emotion_tags`
- `scene_tags`
- `material_type`

上传素材时需要选择素材类型、分类、标签、可见性与文件。标签使用英文逗号分隔。

## 编辑器说明

编辑页是沉浸式工作台，不显示全局底部 TabBar，只显示编辑器内部工具栏：

- 模板
- 贴纸
- 文字
- 字体
- 导出

画布使用 Konva 渲染，支持：

- 元素选中
- 拖拽
- 缩放
- 旋转
- 文字修改
- 字体切换
- 贴纸替换
- PNG/JPEG/PDF 导出

AI 自动生成布局可以保留视觉安全留白；用户手动拖拽时使用真实手账页面边界，避免元素完全拖出画布。

## 测试

后端测试：

```bash
cd onepage_backend
make test
```

前端类型检查可使用：

```bash
cd onepage_frontend
npm exec tsc -- --noEmit --incremental false --pretty false
```

## 不建议提交的本地文件

以下通常是素材原始包、日志或构建产物，不建议提交：

- `irasutoya/`
- `shigureni/`
- `素材2.0/`
- `onepage_backend/llm_worker.log`
- `onepage_backend/nohup.out`
- `onepage_backend/onepage_backend.egg-info/`
- `onepage_backend/1~`

## 当前状态

项目仍处于产品原型与集成开发阶段。前端已经形成统一的 onepage 视觉体系；后端已具备 AI pipeline、素材库、任务状态、手账本与页面管理等核心能力。
