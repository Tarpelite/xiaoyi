# 使用官方 uv 镜像提供二进制文件
FROM astral-sh/uv:latest AS uv_bin

# 基础镜像
FROM aqtbrodh2awvkc.xuanyuan.run/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    # 关键：告诉 uv 将包安装到系统 site-packages，而不是创建虚拟环境
    UV_SYSTEM_PYTHON=1 

# 复制 uv 二进制文件到当前镜像
COPY --from=uv_bin /uv /uvx /bin/

# 配置 apt 使用阿里云镜像并安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. 只复制依赖声明文件（利用 Docker 缓存）
# 如果你本地执行了 uv add，建议复制 pyproject.toml 和 uv.lock
# 如果还没切换，可以继续用 requirements.txt
COPY backend/requirements.txt .

# 2. 使用 uv 极速安装
# --index-url 依然可以使用阿里云，但 uv 本身已经非常快
RUN uv pip install --no-cache -r requirements.txt \
    --index-url https://mirrors.aliyun.com/pypi/simple/

# 复制业务代码
COPY backend/app ./app
COPY backend/scripts ./scripts

EXPOSE 8000

# 健康检查保持不变
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]