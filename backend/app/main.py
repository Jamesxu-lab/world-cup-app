import asyncio
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.database import init_db
from app.api.matches import router as matches_router
from app.api.chat import router as chat_router
from app.api.predictions import router as predictions_router
from app.services.prediction_sync import start_prediction_daily_sync_task, sync_prediction_snapshot_on_startup
from app.services.startup_match_sync import sync_yesterday_matches_on_startup
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await sync_yesterday_matches_on_startup()
    startup_prediction_sync_task = await sync_prediction_snapshot_on_startup()
    daily_prediction_sync_task = start_prediction_daily_sync_task()
    try:
        yield
    finally:
        for task in (startup_prediction_sync_task, daily_prediction_sync_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


app = FastAPI(
    title="晨报球搭子 API",
    description="2026世界杯 AI叙事战报服务",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches_router)
app.include_router(chat_router)
app.include_router(predictions_router)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health")
async def root_health_check():
    return {"status": "ok", "version": "0.1.0"}


# ── 前端静态文件服务与 SPA 路由回退（必须在所有 API 路由之后） ──
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    _frontend_assets = _frontend_dist / "assets"
    if _frontend_assets.is_dir():
        # 挂载静态资源目录（JS/CSS/图片等）
        app.mount("/assets", StaticFiles(directory=str(_frontend_assets)), name="static-assets")

    def _frontend_file_response(path: Path, *, no_cache: bool = False) -> FileResponse:
        headers = {"Cache-Control": "no-cache"} if no_cache else None
        return FileResponse(path, headers=headers)

    # SPA 回退路由：根目录静态文件直接返回，其他非 API 路径返回 index.html。
    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa_or_public_asset(path: str):
        if "/" in path:
            index_file = _frontend_dist / "index.html"
            if index_file.exists():
                return _frontend_file_response(index_file, no_cache=True)
            return {"detail": "Frontend not built. Run 'npm run build' in frontend/."}

        asset_file = _frontend_dist / path
        if asset_file.is_file():
            return _frontend_file_response(asset_file, no_cache=asset_file.name == "index.html")

        index_file = _frontend_dist / "index.html"
        if index_file.exists():
            return _frontend_file_response(index_file, no_cache=True)
        return {"detail": "Frontend not built. Run 'npm run build' in frontend/."}
