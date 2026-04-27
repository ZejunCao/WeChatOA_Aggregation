# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: 构建前端（产出 frontend/dist）
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

# 先装依赖，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: 运行时（Python + Chromium + uvicorn）
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:/root/.local/bin:${PATH}" \
    TZ=Asia/Shanghai

# Chromium + 扫码登录所需字体 / 系统库（DrissionPage 无头模式）
# fonts-noto-cjk：保证二维码附近的中文文字能正常渲染
# fonts-noto-color-emoji：防止 emoji 缺字告警
# tzdata：让容器内时间和宿主一致
# ca-certificates / curl：uv / pip 下载依赖与容器健康检查
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        curl \
        tzdata \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
    && ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（用官方独立二进制，避免再引入一层 pip）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# 先只拷依赖清单，最大化利用层缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 预置 DrissionPage 浏览器路径与容器内必要启动参数。
# 写入包内 configs.ini 后，代码中 ChromiumOptions() 会自动继承这些默认值，
# 因此可以保持 api.py 不动（仍然 headless=True + auto_port）。
RUN /opt/venv/bin/python - <<'PY'
from DrissionPage import ChromiumOptions

co = ChromiumOptions()
co.set_browser_path("/usr/bin/chromium")
co.set_argument("--no-sandbox")
co.set_argument("--disable-dev-shm-usage")
co.set_argument("--disable-gpu")
co.save()
print("DrissionPage configs.ini saved.")
PY

# 拷项目代码与构建产物
COPY api.py server.py main.py ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# data 目录用来挂宿主卷（凭证 / 文章 / 封面 / 日志 / LLM 配置）
RUN mkdir -p /app/data/covers

EXPOSE 8000

# 健康检查：命中一个轻量 GET；FastAPI 的 /docs 一定在
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/docs >/dev/null || exit 1

# 生产入口：server.py 会自动挂载前端 dist 与 /data
CMD ["/opt/venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
