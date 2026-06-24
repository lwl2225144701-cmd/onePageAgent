import asyncio
import json
import time
import structlog

logger = structlog.get_logger(__name__)


class AIOrchestrator:
    """Coordinates the 6-step AI pipeline with progressive SSE updates."""

    async def run(self, task_id: str, user_id: str, input_json: dict) -> dict:
        logger.info("orchestrator_run_start", task_id=task_id, user_id=user_id)
        print(f"ORCH_START task_id={task_id}", flush=True)
        total_started = time.perf_counter()
        timings: dict[str, int] = {}
        ctx = {
            "task_id": task_id,
            "user_id": user_id,
            "input_json": input_json,
        }
        from app.ai.mcp_client import journal_context_from_input

        ctx["journal_context"] = journal_context_from_input(input_json, task_id=task_id)

        try:
            await self._publish_progress(task_id, 0, "开始分析", "processing", 0)

            await self._publish_progress(task_id, 1, "内容、情绪与风格分析", "processing", 5)
            logger.info("orchestrator_step_start", task_id=task_id, step=1, step_name="统一内容分析")
            self._print_step(task_id, 1, "统一内容分析", "START")
            step_started = time.perf_counter()
            ctx["step1"] = await self._run_step1(ctx)
            analysis_ms = _elapsed_ms(step_started)
            timings["semantic_ms"] = analysis_ms
            timings["emotion_ms"] = 0
            timings["style_ms"] = 0
            ctx["step2"] = dict(ctx["step1"].get("sentiment") or {})
            ctx["step3"] = dict(ctx["step1"].get("style") or {})
            await self._publish_progress(task_id, 1, "内容理解", "completed", 24)
            await self._publish_progress(task_id, 2, "情感分析", "completed", 32)
            await self._publish_progress(task_id, 3, "风格推断", "completed", 48)
            logger.info("orchestrator_step_done", task_id=task_id, step=1, step_name="统一内容分析")
            self._print_step(task_id, 1, "统一内容分析", "DONE")

            from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

            ctx["visual_brief"] = build_visual_brief_from_context(ctx).model_dump(mode="json")
            print(
                "ONEPAGE_VISUAL_BRIEF "
                f"task_id={task_id} brief={json.dumps(ctx['visual_brief'], ensure_ascii=False)}",
                flush=True,
            )

            # Step 4: Material Matching
            await self._publish_progress(task_id, 4, "素材匹配", "processing", 52)
            logger.info("orchestrator_step_start", task_id=task_id, step=4, step_name="素材匹配")
            self._print_step(task_id, 4, "素材匹配", "START")
            step_started = time.perf_counter()
            ctx["step4"] = await self._run_step4(ctx)
            timings["recall_ms"] = _elapsed_ms(step_started)
            await self._publish_progress(task_id, 4, "素材匹配", "completed", 64)
            logger.info("orchestrator_step_done", task_id=task_id, step=4, step_name="素材匹配")
            self._print_step(task_id, 4, "素材匹配", "DONE")

            # Step 4.5: Material Review
            await self._publish_progress(task_id, 4, "素材审稿", "processing", 65)
            logger.info("orchestrator_step_start", task_id=task_id, step=4.5, step_name="素材审稿")
            self._print_step(task_id, 4, "素材审稿", "REVIEW_START")
            step_started = time.perf_counter()
            ctx["step4_review"] = await self._run_step4_review(ctx)
            timings["review_ms"] = _elapsed_ms(step_started)
            await self._publish_progress(task_id, 4, "素材审稿", "completed", 67)
            logger.info("orchestrator_step_done", task_id=task_id, step=4.5, step_name="素材审稿")
            self._print_step(task_id, 4, "素材审稿", "REVIEW_DONE")

            # Step 5: Layout Generation
            await self._publish_progress(task_id, 5, "排版生成", "processing", 68)
            logger.info("orchestrator_step_start", task_id=task_id, step=5, step_name="排版生成")
            self._print_step(task_id, 5, "排版生成", "START")
            step_started = time.perf_counter()
            ctx["step5"] = await self._run_step5(ctx)
            timings["layout_ms"] = _elapsed_ms(step_started)
            await self._publish_progress(task_id, 5, "排版生成", "completed", 80)
            logger.info("orchestrator_step_done", task_id=task_id, step=5, step_name="排版生成")
            self._print_step(task_id, 5, "排版生成", "DONE")

            # Step 6: Validate & Repair
            await self._publish_progress(task_id, 6, "JSON校验与修复", "processing", 84)
            logger.info("orchestrator_step_start", task_id=task_id, step=6, step_name="JSON校验与修复")
            self._print_step(task_id, 6, "JSON校验与修复", "START")
            step_started = time.perf_counter()
            final_layout = await self._run_step6(ctx)
            timings["validate_ms"] = _elapsed_ms(step_started)
            await self._publish_progress(task_id, 6, "JSON校验与修复", "completed", 95)
            logger.info("orchestrator_step_done", task_id=task_id, step=6, step_name="JSON校验与修复")
            self._print_step(task_id, 6, "JSON校验与修复", "DONE")

            # Final save to DB
            await self._save_result(task_id, user_id, final_layout, ctx.get("step4_review") or ctx.get("step4"))

            await self._publish_progress(task_id, 0, "完成", "completed", 100)
            logger.info("orchestrator_run_done", task_id=task_id)
            print(
                "TASK_DONE "
                f"task_id={task_id} total_ms={_elapsed_ms(total_started)} "
                f"semantic_ms={timings.get('semantic_ms', 0)} "
                f"emotion_ms={timings.get('emotion_ms', 0)} "
                f"style_ms={timings.get('style_ms', 0)} "
                f"recall_ms={timings.get('recall_ms', 0)} "
                f"review_ms={timings.get('review_ms', 0)} "
                f"layout_ms={timings.get('layout_ms', 0)} "
                f"validate_ms={timings.get('validate_ms', 0)}",
                flush=True,
            )
            return final_layout

        except Exception as e:
            logger.exception("orchestrator_run_error", task_id=task_id, error=str(e))
            from app.ai.layout_v2.compiler import compile_emergency_minimal_v2

            fallback = compile_emergency_minimal_v2(task_id=task_id, input_json=input_json)
            await self._save_error(task_id, str(e))
            await self._publish_progress(task_id, 0, "出错", "failed", 0)
            return fallback

    def _print_step(self, task_id: str, step: int, step_name: str, status: str) -> None:
        print(f"STEP {step} {status} task_id={task_id} name={step_name}", flush=True)

    def run_sync(self, task_id: str, user_id: str, input_json: dict) -> dict:
        """Synchronous wrapper for Celery tasks."""
        async def runner() -> dict:
            try:
                return await self.run(task_id, user_id, input_json)
            finally:
                # Celery calls this through asyncio.run(); asyncpg connections are loop-bound.
                # Dispose the pool before the loop closes so the next task does not reuse stale connections.
                try:
                    from app.core.database import engine

                    await engine.dispose()
                except Exception as exc:
                    logger.warning("orchestrator_db_engine_dispose_failed", task_id=task_id, error=str(exc))

        return asyncio.run(runner())

    async def _run_step1(self, ctx):
        from app.ai.pipeline.step1_content import run_content_understanding
        return await run_content_understanding(ctx)

    async def _run_step4(self, ctx):
        from app.ai.pipeline.step4_material import run_material_matching
        return await run_material_matching(ctx)

    async def _run_step4_review(self, ctx):
        from app.ai.pipeline.step4_material_review import run_material_review
        return await run_material_review(ctx)

    async def _run_step5(self, ctx):
        from app.ai.pipeline.step5_layout import run_layout_generation
        return await run_layout_generation(ctx)

    async def _run_step6(self, ctx):
        from app.ai.pipeline.step6_repair import run_validate_and_repair
        return await run_validate_and_repair(ctx)

    async def _publish_progress(self, task_id: str, step: int, step_name: str, status: str, progress: int):
        try:
            import redis.asyncio as aioredis
            from app.config import settings
            from app.services.sse_service import SSEService

            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            sse = SSEService(r)
            await sse.publish_progress(task_id, step, step_name, status, progress)
            logger.debug(
                "orchestrator_progress_published",
                task_id=task_id,
                step=step,
                step_name=step_name,
                status=status,
                progress=progress,
            )
            await r.close()
        except Exception as e:
            logger.exception(
                "orchestrator_progress_publish_failed",
                task_id=task_id,
                step=step,
                step_name=step_name,
                status=status,
                progress=progress,
                error=str(e),
            )
            pass  # SSE is best-effort

    async def _save_result(self, task_id: str, user_id: str, layout: dict, step4: dict | None):
        from sqlalchemy import update
        from app.core.database import async_session_factory
        from app.models.ai_task import AITask
        from app.services.material_service import MaterialService

        async with async_session_factory() as db:
            material_service = MaterialService(db)
            stmt = (
                update(AITask)
                .where(AITask.task_id == task_id)
                .values(status="completed", progress=100, result_json=layout)
            )
            await db.execute(stmt)
            used_urls = material_service.extract_material_urls_from_layout(layout)
            used_count = await material_service.mark_used_by_urls(user_id=user_id, urls=used_urls)
            await db.commit()
        logger.info("orchestrator_result_saved", task_id=task_id, used_material_count=used_count)
        print(
            f"SELECTED_MATERIALS task_id={task_id} items={json.dumps(self._summarize_selected_materials(used_urls, step4), ensure_ascii=False)}",
            flush=True,
        )

    def _summarize_selected_materials(self, used_urls: list[str], step4: dict | None) -> list[dict]:
        if not used_urls or not isinstance(step4, dict):
            return []

        candidates_by_url: dict[str, dict] = {}
        role_groups = step4.get("role_groups")
        if isinstance(role_groups, dict):
            for role, items in role_groups.items():
                for item in items if isinstance(items, list) else []:
                    if not isinstance(item, dict):
                        continue
                    candidate = {**item, "safe_role": role}
                    for key in ("file_url", "raw_file_url", "preview_url"):
                        url = str(candidate.get(key) or "").strip()
                        if url:
                            candidates_by_url[url] = candidate
        for group in step4.get("groups", []):
            if not isinstance(group, dict):
                continue
            for item in group.get("items", []):
                if not isinstance(item, dict):
                    continue
                for key in ("file_url", "raw_file_url", "preview_url"):
                    url = str(item.get(key) or "").strip()
                    if url:
                        candidates_by_url[url] = item

        selected: list[dict] = []
        for url in used_urls:
            item = candidates_by_url.get(url)
            if item is None:
                continue
            selected.append(
                {
                    "material_id": item.get("material_id"),
                    "type": item.get("material_type"),
                    "role": item.get("role") or item.get("safe_role") or item.get("suggested_role"),
                    "name": item.get("display_name") or item.get("origin_path"),
                    "category": item.get("category"),
                }
            )
        return selected

    async def _save_error(self, task_id: str, error: str):
        from sqlalchemy import update
        from app.core.database import async_session_factory
        from app.models.ai_task import AITask

        async with async_session_factory() as db:
            stmt = (
                update(AITask)
                .where(AITask.task_id == task_id)
                .values(status="failed", progress=0, error_message=error)
            )
            await db.execute(stmt)
            await db.commit()
        logger.info("orchestrator_error_saved", task_id=task_id, error=error)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
