# amap-weather-mcp

`amap-weather-mcp` 是 onepage 手帐 APP 的 MCP 工具服务，用于给 AI 自动编排提供当前地点、日期时间、天气和天气素材语义上下文。

服务只负责工具能力，不改动现有业务主流程。

## 功能

- 通过高德 IP 定位获取当前城市。
- 根据城市、区县、行政区名称解析高德 `adcode`。
- 获取当前真实日期、时间、星期和时区。
- 查询高德实时天气。
- 在工具层完成天气图标映射。
- 输出手帐页顶部可直接使用的日期、天气、图标和素材推荐标签。

## 环境变量

默认推荐把高德 Key 和 MCP 监听配置统一维护在项目的 `onepage_backend/.env`，启动命令里不需要再显式传 Key。仓库不再维护 MCP 子目录的重复 `.env.example`，需要示例时直接看 `onepage_backend/.env.example`。

`mcp/amap_weather/.env` 仍然兼容，但只建议在单独调试 MCP 服务时临时覆盖使用；日常不要在这里维护第二份配置。

MCP 服务读取顺序如下，先读到的值优先：

1. `onepage_backend/.env`
2. 项目根目录 `.env`
3. `mcp/amap_weather/.env`（仅单独调试时使用）

建议在 `onepage_backend/.env` 中维护：

```bash
AMAP_WEB_SERVICE_KEY=你的高德Web服务Key
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_PATH=/mcp
DEFAULT_TIMEZONE=Asia/Shanghai
```

说明：

- `AMAP_WEB_SERVICE_KEY`：高德 Web 服务 Key，放在本地 `onepage_backend/.env`，不要提交到 Git。
- `MCP_TRANSPORT`：`stdio` 或 `http`，默认 `http`。
- `MCP_HOST` / `MCP_PORT` / `MCP_PATH`：`http` 模式监听地址和 MCP 路径，默认 `127.0.0.1:8001/mcp`。
- `MCP_HTTP_HOST` / `MCP_HTTP_PORT`：兼容旧变量，优先级低于 `MCP_HOST` / `MCP_PORT`。
- `DEFAULT_TIMEZONE`：默认 `Asia/Shanghai`。

## 安装依赖

建议在独立虚拟环境中安装：

```bash
cd /项目路径/mcp/amap_weather
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## stdio 启动

```bash
cd /项目路径/mcp/amap_weather
MCP_TRANSPORT=stdio python server.py
```

## http 启动

```bash
cd /项目路径/mcp/amap_weather
python server.py
```

如果 `onepage_backend/.env` 中已经配置了 `MCP_TRANSPORT=http`、`MCP_HOST=127.0.0.1`、`MCP_PORT=8001` 和 `MCP_PATH=/mcp`，HTTP 模式只需要执行 `python server.py`。

`http` 模式使用 MCP SDK 的 `streamable-http` 传输，不额外引入 FastAPI 或 Flask。

业务后端、Celery Worker 和连通性检查脚本使用同一个地址：

```bash
AMAP_WEATHER_MCP_URL=http://127.0.0.1:8001/mcp
MCP_TOOL_TIMEOUT_SECONDS=10
```

## 连通性检查

启动 http 模式后，可以检查 `list_tools` 和 `journal_page_context` 是否可用：

```bash
cd /项目路径
python scripts/check_amap_weather_mcp.py
```

检查脚本会读取 `onepage_backend/.env` 中的 `AMAP_WEATHER_MCP_URL` 和 `MCP_TOOL_TIMEOUT_SECONDS`。

## MCP 客户端注册示例

```json
{
  "mcpServers": {
    "amap-weather": {
      "command": "python",
      "args": ["/项目路径/mcp/amap_weather/server.py"],
      "env": {
        "AMAP_WEB_SERVICE_KEY": "你的高德Web服务Key",
        "MCP_TRANSPORT": "stdio",
        "DEFAULT_TIMEZONE": "Asia/Shanghai"
      }
    }
  }
}
```

## 工具列表

### `amap_get_current_location()`

通过高德 IP 定位获取当前城市、省份、`adcode` 和定位来源。

### `amap_resolve_district(location: str)`

根据用户输入的城市、区县或行政区名称解析高德行政区信息。

### `journal_get_current_datetime(timezone: str | None = None)`

返回服务运行时的真实当前日期、时间、中文星期和 ISO 时间。

### `amap_current_weather(location: str | None = None)`

查询实时天气。传入 `location` 时优先解析行政区；不传时先通过 IP 定位。

### `journal_page_context(location: str | None = None, timezone: str | None = None)`

推荐给手帐生成调用的一站式工具，返回日期、地点、天气、天气图标和素材推荐标签。

## `journal_page_context` 返回示例

```json
{
  "source": "journal_mcp",
  "ok": true,
  "type": "journal_page_context",
  "datetime": {
    "date": "2026-06-13",
    "time": "14:30",
    "weekday": "星期六",
    "timezone": "Asia/Shanghai",
    "iso_datetime": "2026-06-13T14:30:00+08:00"
  },
  "location": {
    "province": "广东省",
    "city": "深圳市",
    "adcode": "440300",
    "location_source": "amap_ip"
  },
  "weather": {
    "text": "晴",
    "icon": "☀️",
    "icon_key": "sunny",
    "temperature_celsius": "28",
    "humidity": "66",
    "wind_direction": "东南",
    "wind_power": "≤3",
    "report_time": "2026-06-13 14:00:00"
  },
  "journal_header": {
    "date_text": "2026-06-13",
    "weather_text": "晴",
    "weather_icon": "☀️"
  },
  "semantic_tags": ["晴天", "阳光", "明亮"],
  "mood_tags": ["清爽", "元气", "轻快"],
  "recommended_material_tags": ["太阳", "蓝天", "光斑", "暖色贴纸"]
}
```

## 天气图标

工具层会返回 `weather_icon` 和 `weather_icon_key`，AI 和前端不需要自行猜图标。

- 晴：`☀️` / `sunny`
- 少云、晴间多云：`🌤️` / `partly_sunny`
- 多云：`⛅` / `cloudy_sunny`
- 阴：`☁️` / `overcast`
- 雨：`🌧️` / `rain`
- 雷阵雨：`⛈️` / `thunderstorm`
- 雪：`❄️` / `snow`
- 雾、霾、浮尘、扬沙、沙尘暴：`🌫️` / `fog`
- 风：`💨` / `wind`
- 未知：`🌈` / `unknown`

## AI 调用策略

1. 用户要求生成手帐页面，且页面需要日期、天气、地点信息时，优先调用 `journal_page_context`。
2. 用户只问当前天气时，调用 `amap_current_weather`。
3. 用户只需要当前日期时间时，调用 `journal_get_current_datetime`。
4. 用户没有提供地点时，先尝试 `amap_get_current_location`。
5. 如果自动定位失败，再要求用户补充城市。
6. AI 不允许编造当前日期和天气。
7. AI 拿到 `journal_page_context` 后，再自主进行素材选择、文案生成、布局编排。

## 错误返回

所有工具都返回稳定 JSON：

```json
{
  "ok": false,
  "source": "amap",
  "type": "current_weather",
  "error_type": "AMAP_API_ERROR",
  "message": "高德接口返回错误。"
}
```

常见错误类型：

- `MISSING_AMAP_KEY`
- `LOCATION_RESOLVE_FAILED`
- `DISTRICT_NOT_FOUND`
- `AMAP_API_ERROR`
- `AMAP_HTTP_TIMEOUT`
- `AMAP_HTTP_ERROR`
- `INVALID_RESPONSE`
- `UNKNOWN_ERROR`
