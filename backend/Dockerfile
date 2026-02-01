# 使用官方 uv 镜像作为构建阶段
FROM astral-sh/uv:latest AS uv_bin

# 基础镜像
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    UV_SYSTEM_PYTHON=1

# 复制 uv 二进制文件
COPY --from=uv_bin /uv /uvx /bin/

# 配置 apt 使用阿里云镜像并安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制项目依赖配置
COPY backend/pyproject.toml backend/uv.lock* ./

# 安装依赖
# 注意：由于 pyproject.toml 可能被手动修改，这里不强制 --frozen
# uv sync 会创建 .venv，CMD 使用 uv run 调用
RUN uv sync --no-install-project

# 复制业务代码
COPY backend/app ./app
COPY backend/scripts ./scripts

# 复制环境变量文件 (User requested)
COPY backend/.env* ./

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 使用 uv run 启动
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]