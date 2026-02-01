# ============================================
# 后端 Dockerfile - 优化版 (使用轩辕镜像加速)
# ============================================

# 1. 使用轩辕镜像仓库的基础镜像
FROM aqtbrodh2awvkc.xuanyuan.run/python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    UV_SYSTEM_PYTHON=1 \
    # 允许 uv 在没有虚拟环境的情况下安装到系统路径
    UV_LINK_MODE=copy

# 2. 配置系统源与工具安装
# 使用阿里云 APT 镜像加速系统组件安装
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 uv (使用阿里云 PyPI 镜像加速)
RUN pip install uv -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

WORKDIR /app

# 4. 利用 Docker 层缓存安装依赖
# 先复制依赖定义文件
COPY backend/pyproject.toml backend/uv.lock* ./

# 执行依赖同步 (指定镜像源加速下载)
# --no-install-project 表示只安装依赖，不安装当前项目代码
WORKDIR /app

# 复制依赖配置
COPY backend/pyproject.toml backend/uv.lock* ./

# 【关键修改】增加 --no-python-downloads 阻止其下载 Python
# 增加 --python /usr/local/bin/python 明确指向基础镜像的 Python
RUN uv sync \
    --no-install-project \
    --no-python-downloads \
    --python /usr/local/bin/python \
    --index-url https://mirrors.aliyun.com/pypi/simple/

# 5. 复制业务代码与配置
# 复制生成的 .env 文件（确保 GitHub Actions 已生成该文件）
COPY backend/.env* ./
# 复制应用逻辑
COPY backend/app ./app
COPY backend/scripts ./scripts

EXPOSE 8000

# 6. 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 7. 启动服务
# 使用 uv run 确保环境隔离和依赖正确加载
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]