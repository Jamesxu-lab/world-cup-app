"""
冠军预测 API 路由
"""
import json
from pathlib import Path

from fastapi import APIRouter, Query

from app.services.prediction_model import MODEL_VERSION, build_prediction, get_prediction_inputs_mtime


router = APIRouter(prefix="/api/v1", tags=["predictions"])
DEFAULT_ITERATIONS = 10000
DEFAULT_SEED = 2026
CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "champion_prediction_cache.json"


def _cache_is_fresh() -> bool:
    if not CACHE_PATH.exists():
        return False
    if CACHE_PATH.stat().st_mtime < get_prediction_inputs_mtime():
        return False
    return True


def _read_cached_prediction() -> dict | None:
    if not _cache_is_fresh():
        return None
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("iterations") != DEFAULT_ITERATIONS:
        return None
    if payload.get("model_version") != MODEL_VERSION:
        return None
    return payload


def _write_cached_prediction(payload: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


@router.get("/predictions/champion")
async def champion_prediction(
    iterations: int = Query(DEFAULT_ITERATIONS, ge=1000, le=50000, description="蒙特卡洛模拟次数"),
    seed: int = Query(DEFAULT_SEED, description="随机种子，用于复现实验结果"),
):
    """获取 2026 世界杯冠军概率预测"""
    if iterations == DEFAULT_ITERATIONS and seed == DEFAULT_SEED:
        cached = _read_cached_prediction()
        if cached:
            return cached
        prediction = build_prediction(iterations=iterations, seed=seed)
        _write_cached_prediction(prediction)
        return prediction

    return build_prediction(iterations=iterations, seed=seed)
