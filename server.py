#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生产环境 ASGI 入口：复用 api.app，并额外挂载前端 dist 与 data/ 静态目录。

开发时仍然使用 `uv run uvicorn api:app`（前端由 Vite 开发服通过 /api 代理打到后端）。
生产 / Docker 场景则运行 `uvicorn server:app`，前后端同域：

  /api/*     → FastAPI 业务路由（见 api.py）
  /data/*    → data 目录下的 JSON 与封面图等只读资源
  /*         → frontend/dist 下的 SPA 静态资源（hash 路由，index.html 兜底）
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from api import app

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
COVERS_DIR = DATA_DIR / "covers"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

DATA_DIR.mkdir(parents=True, exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)


@app.middleware("http")
async def no_cache_data_json(request: Request, call_next) -> Response:
    """爬取会更新 data/*.json；禁止浏览器缓存，避免配置页/文章页显示旧数据。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/data/") and path.endswith(".json"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


# /data 挂载：封面图 `/data/covers/`；凭证与 LLM 配置 JSON 亦在此目录（勿公网暴露）。
# 注意：此目录里的 id_info.json / llm_config.json 等也会被暴露，
# 仅适用于「本机自托管，不对外开放」的使用场景（与 README 的定位一致）。
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# 前端 dist 挂到根路径；html=True 让 `/` 自动返回 index.html。
# 前端使用 hash 路由（#/config），因此不需要 SPA history fallback。
if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )
else:
    import logging

    logging.getLogger(__name__).warning(
        "frontend/dist 不存在，跳过前端静态挂载；生产构建请先执行 `npm run build`。"
    )
