# OnePage 前后端联调策略

## 目标

把当前前端 MVP 从本地 mock 闭环，逐步切到 `onepage_backend` 的真实接口，同时保留无后端时可演示的降级体验。

核心链路：

```text
输入内容 -> 上传资源 -> 创建 AI 任务 -> SSE 监听 -> 获取 Layout JSON -> Konva 渲染/编辑 -> 保存 Page -> 手账本展示 -> 导出
```

## 环境约定

前端目录：`onepage_frontend`

后端目录：`onepage_backend`

前端环境变量：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

后端 API 前缀来自 `app/config.py`：

```text
API_V1_PREFIX=/api
```

匿名用户策略：

后端通过 `X-Anonymous-User-Id` 识别匿名用户。前端已在 `src/api/client.ts` 里生成并持久化匿名 ID，所有 Axios 请求会自动带上该 header。

## 模块对齐

| 后端资源 | 后端路由 | 前端文件 | 前端模块 |
| --- | --- | --- | --- |
| 上传 | `POST /uploads/image`, `POST /uploads/audio` | `src/api/uploads.api.ts` | `modules/create` |
| AI 任务 | `POST /ai/tasks`, `GET /ai/tasks/{id}`, `GET /ai/tasks/{id}/events` | `src/api/ai-tasks.api.ts` | `modules/ai` |
| 手账本 | `GET/POST /journals` | `src/api/journals.api.ts` | `modules/journal` |
| 页面 | `POST/PUT/GET/DELETE /pages` | `src/api/pages.api.ts` | `modules/editor` |
| 素材 | `GET /materials`, `GET /materials/recommend` | `src/api/materials.api.ts` | `modules/materials`, `modules/editor` |
| 天气 | `GET /weather` | `src/api/weather.api.ts` | `modules/create` |
| 导出 | `POST /export` | `src/api/export.api.ts` | `modules/editor` |

## 联调顺序

### 1. 健康检查和 CORS

先验证后端基础可用：

```bash
curl http://localhost:8000/health
```

预期：

```json
{"status":"ok"}
```

前端请求后端时如果出现 CORS、404、连接失败，优先检查：

- 后端是否跑在 `8000`
- `.env.local` 的 `NEXT_PUBLIC_API_BASE_URL`
- 后端 `API_V1_PREFIX` 是否仍为 `/api`

### 2. 匿名用户 header

验证任意需要用户的接口是否收到稳定匿名用户：

```bash
curl -H "X-Anonymous-User-Id: local-test-user" http://localhost:8000/api/journals
```

前端要求：

- 首次打开生成 anonymous id
- 后续刷新仍使用同一个 id
- 不在业务模块里手写 header，统一走 `apiClient`

### 3. 上传链路

前端位置：`modules/create/create-view.tsx`

联调路径：

```text
选择图片 -> uploadImage(file) -> 得到 file_url -> createAiTask(input_json.image_urls)
```

验收：

- 图片类型限制由后端校验，前端先只限制 `accept=image/*`
- 上传失败时保留本地 mock，不阻断用户进入生成演示
- 成功时 `image_urls` 使用后端返回的 `file_url`

### 4. AI 任务与 SSE

前端位置：

- `src/api/ai-tasks.api.ts`
- `src/modules/ai/loading-view.tsx`
- `src/stores/ai-task-store.ts`

联调路径：

```text
POST /ai/tasks
-> 返回 task_id
-> EventSource 连接 /ai/tasks/{task_id}/events
-> 更新 progress / stepName
-> progress 100 后 GET /ai/tasks/{task_id}
-> result_json 写入 editorStore.layout
```

注意：

当前后端 SSE endpoint 使用 path 参数，不通过 Axios，所以 header 不能直接注入。若后端严格依赖 header，需要二选一：

1. 后端允许 SSE 通过 query 参数传匿名用户。
2. 前端改用 `fetch` 流式读取，手动带 header。

当前前端 `createEventSource` 已把匿名 id 放进 query，后端若暂不读取该 query，也不影响按 `task_id` 订阅。

### 5. Layout JSON 到 Konva

后端 fallback layout 结构：

```ts
{
  page: { width, height, background },
  elements: [
    { type, props, z_index }
  ],
  style?: {}
}
```

前端渲染位置：`src/modules/editor/journal-canvas.tsx`

第一阶段支持元素：

- `text`
- `image`
- `sticker`
- `decoration`
- `date_tag`
- `mood_tag`

当前已支持 `text / image / sticker`。联调 AI 真实结果前，需要补齐 `date_tag / mood_tag / decoration` 的映射，未知类型降级成 sticker 或忽略并记录 console warning。

### 6. 保存页面

前端位置：`modules/editor/editor-view.tsx`

后端要求：

```ts
POST /pages
{
  journal_id,
  title,
  content_text,
  layout_json,
  elements,
  weather,
  mood,
  page_date
}
```

联调策略：

第一阶段：

```text
如果没有 journal -> POST /journals 创建默认 "2024 手账本"
保存当前 layout_json 到 POST /pages
```

第二阶段：

```text
进入编辑器前加载/选择 journal_id
保存时 PUT /pages/{page_id}
```

### 7. 手账本列表

前端位置：`modules/journal/library-view.tsx`

联调路径：

```text
GET /journals -> 展示书架
GET /journals/{journal_id} -> 展示 pages brief
```

当前前端只接了 `GET /journals`，月历页仍是本地占位。下一步要补 `getJournalDetail(journalId)` API，然后把月份统计从 `pages.page_date` 计算出来。

### 8. 素材推荐

前端位置：`modules/materials/materials-view.tsx`

联调路径：

```text
GET /materials/recommend?style=healing&emotion=happy&scene=sea
```

编辑器贴纸面板后续应从推荐素材读取，而不是固定数组。

### 9. 导出

前端位置：`modules/editor/editor-panels.tsx`

第一阶段：

```text
Konva Stage.toDataURL() 本地导出 PNG
```

第二阶段：

```text
POST /export { page_id, format }
-> 返回 export task_id
-> 轮询或后续补导出状态接口
```

当前后端只有创建导出任务接口，没有查询导出任务结果接口。若要完整联调导出下载，需要后端补：

```text
GET /export/{task_id}
```

## Mock 切换策略

前端不建议删除 mock，而是做 API 失败降级：

- 后端可用：走真实接口
- 后端不可用：保持本地演示 flow

当前已经采用这个策略：

- `createAiTask` 失败时进入 `mock-task`
- `listJournals` 失败时展示本地/占位书架
- `recommendMaterials` 失败时展示占位素材
- `createPage` 失败时写入本地 Zustand page

## 当前需要补齐的前端事项

1. `journals.api.ts` 增加 `getJournal(journalId)`。
2. `journal-store` 增加 `selectedJournalId`。
3. `journal-canvas` 补齐后端元素类型：`date_tag / mood_tag / decoration`。
4. `editor` 保存时把 Konva 元素转换为后端 `elements: ElementDTO[]`。
5. `export` 面板接入 `createExport`，本地 PNG 导出作为 fallback。
6. 上传图片后在 Konva image 元素中真实渲染图片，而不是白色占位。

## 当前需要确认的后端事项

1. SSE 是否需要用户鉴权。如果需要，建议支持 query token 或改成 fetch stream。
2. `GET /ai/tasks/{task_id}` 从 Redis 返回时，当前可能缺少 `input_json/user_id` 字段，和 `TaskDetailResponse` 不完全一致，需要确认。
3. `MaterialResponse` schema 中字段是 `meta_info`，路由返回使用了 `metadata`，需要统一字段名。
4. `JournalService` 末尾有 `Journal.pages = None`，但接口里使用 `selectinload(Journal.pages)`，需要确认 relationship 是否完整。
5. 导出任务缺少查询/下载接口，前端只能创建任务，无法拿结果。

## 验收清单

### 最小联调通过

- 前端 `npm run dev` 打开首页
- 输入文本并选择图片
- 图片上传成功，拿到 `file_url`
- 创建 AI task 成功，拿到 `task_id`
- loading 页收到 SSE progress
- task 完成后拿到 `result_json`
- Konva 渲染 layout
- 保存 page 成功
- 手账本页能看到新 page 所属 journal

### 可降级演示

- 后端关闭时，前端仍能完成：输入 -> mock 生成 -> 编辑 -> 本地保存 -> 手账本占位展示

