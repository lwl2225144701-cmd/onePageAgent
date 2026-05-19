import asyncio
import json
import structlog

from app.ai.fallback.templates import get_fallback_layout

logger = structlog.get_logger(__name__)


class AIOrchestrator:
    """Coordinates the 6-step AI pipeline with progressive SSE updates."""

    async def run(self, task_id: str, user_id: str, input_json: dict) -> dict:
        logger.info("orchestrator_run_start", task_id=task_id, user_id=user_id)
        ctx = {
            "task_id": task_id,
            "user_id": user_id,
            "input_json": input_json,
        }

        try:
            await self._publish_progress(task_id, 0, "开始分析", "processing", 0)

            # Step 1: Content Understanding
            await self._publish_progress(task_id, 1, "内容理解", "processing", 5)
            logger.info("orchestrator_step_start", task_id=task_id, step=1, step_name="内容理解")
            ctx["step1"] = await self._run_step1(ctx)
            await self._publish_progress(task_id, 1, "内容理解", "completed", 16)
            logger.info("orchestrator_step_done", task_id=task_id, step=1, step_name="内容理解")

            # Step 2: Sentiment Analysis
            await self._publish_progress(task_id, 2, "情感分析", "processing", 20)
            logger.info("orchestrator_step_start", task_id=task_id, step=2, step_name="情感分析")
            ctx["step2"] = await self._run_step2(ctx)
            await self._publish_progress(task_id, 2, "情感分析", "completed", 32)
            logger.info("orchestrator_step_done", task_id=task_id, step=2, step_name="情感分析")

            # Step 3: Style Inference
            await self._publish_progress(task_id, 3, "风格推断", "processing", 36)
            logger.info("orchestrator_step_start", task_id=task_id, step=3, step_name="风格推断")
            ctx["step3"] = await self._run_step3(ctx)
            await self._publish_progress(task_id, 3, "风格推断", "completed", 48)
            logger.info("orchestrator_step_done", task_id=task_id, step=3, step_name="风格推断")

            # Step 4: Material Matching
            await self._publish_progress(task_id, 4, "素材匹配", "processing", 52)
            logger.info("orchestrator_step_start", task_id=task_id, step=4, step_name="素材匹配")
            ctx["step4"] = await self._run_step4(ctx)
            await self._publish_progress(task_id, 4, "素材匹配", "completed", 64)
            logger.info("orchestrator_step_done", task_id=task_id, step=4, step_name="素材匹配")

            # Step 5: Layout Generation
            await self._publish_progress(task_id, 5, "排版生成", "processing", 68)
            logger.info("orchestrator_step_start", task_id=task_id, step=5, step_name="排版生成")
            ctx["step5"] = await self._run_step5(ctx)
            await self._publish_progress(task_id, 5, "排版生成", "completed", 80)
            logger.info("orchestrator_step_done", task_id=task_id, step=5, step_name="排版生成")

            # Step 6: Validate & Repair
            await self._publish_progress(task_id, 6, "JSON校验与修复", "processing", 84)
            logger.info("orchestrator_step_start", task_id=task_id, step=6, step_name="JSON校验与修复")
            final_layout = await self._run_step6(ctx)
            await self._publish_progress(task_id, 6, "JSON校验与修复", "completed", 95)
            logger.info("orchestrator_step_done", task_id=task_id, step=6, step_name="JSON校验与修复")

            # Final save to DB
            await self._save_result(task_id, final_layout)

            await self._publish_progress(task_id, 0, "完成", "completed", 100)
            logger.info("orchestrator_run_done", task_id=task_id)
            return final_layout

        except Exception as e:
            logger.exception("orchestrator_run_error", task_id=task_id, error=str(e))
            fallback = get_fallback_layout("neutral")
            await self._save_error(task_id, str(e))
            await self._publish_progress(task_id, 0, "出错", "failed", 0)
            return fallback

    def run_sync(self, task_id: str, user_id: str, input_json: dict) -> dict:
        """Synchronous wrapper for Celery tasks."""
        return asyncio.run(self.run(task_id, user_id, input_json))

    async def _run_step1(self, ctx):
        from app.ai.pipeline.step1_content import run_content_understanding
        return await run_content_understanding(ctx)

    async def _run_step2(self, ctx):
        from app.ai.pipeline.step2_sentiment import run_sentiment_analysis
        return await run_sentiment_analysis(ctx)

    async def _run_step3(self, ctx):
        from app.ai.pipeline.step3_style import run_style_inference
        return await run_style_inference(ctx)

    async def _run_step4(self, ctx):
        from app.ai.pipeline.step4_material import run_material_matching
        return await run_material_matching(ctx)

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
            logger.info(
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

    async def _save_result(self, task_id: str, layout: dict):
        from sqlalchemy import update
        from app.core.database import async_session_factory
        from app.models.ai_task import AITask

        async with async_session_factory() as db:
            stmt = (
                update(AITask)
                .where(AITask.task_id == task_id)
                .values(status="completed", progress=100, result_json=layout)
            )
            await db.execute(stmt)
            await db.commit()
        logger.info("orchestrator_result_saved", task_id=task_id)

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
