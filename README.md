# Xiaoyi Guess (小易猜猜)

<div align="center">

<img src="frontend/public/logo.png" width="10%" alt="Logo">

**Xiaoyi Guess**

*Just typing, Just guessing, Just staring*  
*即聊，即猜，即看*

[![Demo](https://img.shields.io/badge/Demo-Live-blue)](https://xiaoyi.actscal.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Tarpelite/xiaoyi?style=social)](https://github.com/Tarpelite/xiaoyi/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/Tarpelite/xiaoyi?style=social)](https://github.com/Tarpelite/xiaoyi/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/Tarpelite/xiaoyi?style=social)](https://github.com/Tarpelite/xiaoyi/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/Tarpelite/xiaoyi)](https://github.com/Tarpelite/xiaoyi/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Tarpelite/xiaoyi)](https://github.com/Tarpelite/xiaoyi/pulls)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/uv-Latest-DE5FE9?logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![pnpm](https://img.shields.io/badge/pnpm-8+-F69220?logo=pnpm&logoColor=white)](https://pnpm.io/)

[在线演示](https://xiaoyi.actscal.org) · [技术文档](#技术架构) · [快速开始](#快速启动)

</div>

---

## 📖 项目简介

**Xiaoyi Guess (小易猜猜)** 是一个基于大语言模型（LLM）调度时序专用小模型的智能时间序列分析与预测平台。通过融合前沿的Transformer架构、专业时序模型和检索增强生成（RAG）技术，为时间序列数据提供可解释的深度分析和精准预测。

### 🎯 两大核心能力

#### 📊 **时序分析 (Time Series Analysis)**

对历史时间序列进行自适应深度分析，自动识别趋势事件并进行评价分析，智能切分语义区间，解析历史态势趋势。

**核心特性**：
- **事件自动识别与标注**：基于特征工程自动检测时序数据中的关键事件点
- **关键区间智能切分**：采用自适应分割算法识别语义一致的时间区间
- **自然语言态势分析**：利用LLM生成人类可理解的趋势解读和因果推断

#### 🔮 **时序预测 (Time Series Forecasting)**

基于多源信息融合的智能预测框架，不仅提供数值预测结果，更能解释预测背后的逻辑与依据。

**核心特性**：
- **前沿模型集成**：集成Transformer、PatchTST、TimesNet、DLinear等SOTA时序模型
- **可解释性预测**：通过LLM调度引擎生成预测依据和置信度评估
- **多模型融合策略**：基于贝叶斯模型平均（BMA）实现多模型集成预测
- **实时流式响应**：采用服务端事件推送（SSE）技术实现低延迟交互

### 💡 技术亮点

- **LLM智能调度中枢**：DeepSeek驱动的认知引擎，实现自然语言与时序模型的桥接
- **时序预测引擎**：集成Prophet、XGBoost、DLinear等多个时序专用模型
- **知识检索系统**：基于BGE嵌入模型和Qdrant向量数据库的RAG架构
- **实时流式响应**：SSE + Redis消息队列实现亚秒级响应

---

## 🏗️ 技术架构

### 核心设计：LLM调度时序小模型

采用大语言模型（LLM）作为智能调度中枢，统一管理时序数据预处理、模型推理引擎和精准分析流程的一体化架构。实现自然语言理解与专业时序分析的无缝融合。

```mermaid
graph TB
    A[用户自然语言输入] --> B[LLM智能中枢<br/>DeepSeek驱动的认知引擎]
    B --> C[时序预测引擎<br/>Prophet/XGBoost/DLinear]
    B --> D[知识检索系统<br/>BGE嵌入 + Qdrant向量库]
    B --> E[实时流式响应<br/>SSE + Redis消息队列]
    C --> F[多模型融合预测]
    D --> G[领域知识增强]
    E --> H[Web交互界面]
    F --> B
    G --> B
    H --> I[用户体验层]
```

### 模型能力矩阵

**时序预测模型排行榜** (Multivariate Long-Term Forecasting, MSE ↓):

| 排名 | 模型 | 会议/期刊 | AVG MSE | 特点 |
|------|------|----------|---------|------|
| 1 | **iTransformer** | ICLR'24 | 0.311 | 反转Transformer，序列作为Token |
| 2 | **PatchTST** | ICLR'23 | 0.354 | Patch分割 + Self-Attention |
| 3 | **TimesNet** | ICLR'23 | 0.371 | 时域频域双重建模 |
| 4 | **DLinear** | AAAI'23 | 0.415 | 线性模型，高效基线 |
| 5 | **Informer** ⭐ | AAAI'21 Best | 0.448 | ProbSparse注意力机制 |
| 6 | **Autoformer** | NeurIPS'21 | 0.461 | 自相关机制 |

> 数据来源：[OpenTS-Bench](https://github.com/openits/openTS) · 学术支持：Decision Intelligence Lab

### 技术栈全景

#### 后端 (Backend)
- **核心框架**: FastAPI (Python 3.12+) - 高性能异步Web框架
- **包管理器**: `uv` - Rust驱动的极速Python包管理
- **LLM集成**: DeepSeek API, LangChain框架
- **时序模型库**: 
  - Prophet (Facebook) - 可解释的加法模型
  - XGBoost - 梯度提升决策树
  - DLinear - 分解线性模型
  - TimesNet - 时频双域建模
- **知识检索**: 
  - BGE (BAAI General Embedding) - 中英双语嵌入模型
  - Qdrant - 高性能向量数据库
- **数据存储**: 
  - Redis - 内存缓存与消息队列
  - MongoDB - 文档型持久化存储
- **数据来源**: AkShare - 金融数据接口库

#### 前端 (Frontend)
- **核心框架**: Next.js 14 (App Router) - React服务端渲染框架
- **开发语言**: TypeScript 5.0+ - 类型安全的JavaScript超集
- **包管理器**: `pnpm` - 高效的磁盘空间利用
- **UI框架**: 
  - Tailwind CSS - 原子化CSS框架
  - Framer Motion - 声明式动画库
- **图表可视化**: 
  - Recharts - React声明式图表库
  - ECharts - 企业级可视化方案
- **认证系统**: Authing IDaaS - 企业级身份认证服务

#### 实时通信层
- **SSE (Server-Sent Events)**: 服务端主动推送架构
- **Redis Pub/Sub**: 分布式消息订阅模式
- **WebSocket**: 双向实时通信协议（备选）

---

##  快速启动

### 📋 前置要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| **Python** | >= 3.12 | 后端运行环境 |
| **Node.js** | >= 18 | 前端运行环境 |
| **Redis** | >= 7.0 | 缓存服务（必需） |
| **MongoDB** | >= 6.0 | 数据持久化（可选） |
| **uv** 或 **conda** | latest | Python包管理器（二选一） |
| **pnpm** | >= 8.0 | 前端包管理器 |

---

### 🔧 环境配置

#### 1. 克隆项目

```bash
git clone git@github.com:Tarpelite/xiaoyi.git
cd xiaoyi
```

#### 2. 配置环境变量

**后端环境变量** (使用根目录 `.env`):

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入以下必需配置：
# - DEEPSEEK_API_KEY: DeepSeek API密钥（必需）
# - AUTHING_APP_ID: Authing应用ID（必需）
# - AUTHING_APP_SECRET: Authing应用密钥（必需）
# - AUTHING_ISSUER: Authing OIDC地址（必需）
# - MONGODB_HOST/USERNAME/PASSWORD: MongoDB配置（可选）
# - REDIS_HOST/PORT: Redis配置（默认localhost:6379）
```

**前端环境变量** (创建 `frontend/.env.local`):

```bash
# 复制示例文件
cp frontend/.env.local.example frontend/.env.local

# 前端环境变量会自动从根目录.env读取以下内容：
# - NEXT_PUBLIC_API_URL
# - NEXT_PUBLIC_AUTHING_APP_ID
# - NEXT_PUBLIC_AUTHING_ISSUER
# 等等
```

> **💡 提示**: 开发环境下，前端会读取 `frontend/.env.local`，后端会读取根目录 `.env`

#### 3. 启动Redis（必需）

**方式1: Docker (推荐)**
```bash
docker run -d --name xiaoyi-redis \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes
```

**方式2: 本地安装**
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl start redis
```

---

### 🐍 后端启动

#### 方式1: 使用 uv (推荐，极速)

```bash
# 1. 安装 uv（如果未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 进入后端目录
cd backend

# 3. 同步依赖（自动创建虚拟环境）
uv sync

# 4. 启动开发服务器
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ✅ 后端运行在: http://localhost:8000
# 📚 API文档: http://localhost:8000/docs
```

#### 方式2: 使用 Conda

```bash
# 1. 创建虚拟环境
conda create -n xiaoyi python=3.12 -y
conda activate xiaoyi

# 2. 进入后端目录并安装依赖
cd backend
pip install -r requirements.txt

# 3. 启动开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ✅ 后端运行在: http://localhost:8000
```

#### 方式3: 使用 pip + venv

```bash
# 1. 创建虚拟环境
cd backend
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### ⚛️ 前端启动

```bash
# 1. 安装 pnpm（如果未安装）
npm install -g pnpm

# 2. 进入前端目录
cd frontend

# 3. 安装依赖
pnpm install

# 4. 启动开发服务器
pnpm dev

# ✅ 前端运行在: http://localhost:3000
```

**前端开发命令**:
```bash
pnpm dev          # 启动开发服务器
pnpm build        # 生产构建
pnpm start        # 运行生产版本
pnpm lint         # 代码检查
pnpm type-check   # TypeScript类型检查
```

---

### 🐳 Docker部署（一键启动）

使用Docker Compose可以一键启动完整服务（包括Redis、后端、前端）：

```bash
# 1. 确保已配置 .env 文件
cp .env.example .env
# 编辑 .env，填入必需的API密钥

# 2. 构建并启动所有服务
docker compose up -d

# 3. 查看服务状态
docker compose ps

# 4. 查看日志
docker compose logs -f

# ✅ 访问服务:
# - 前端: http://localhost:13000
# - 后端API: http://localhost:18000
# - API文档: http://localhost:18000/docs
```

**Docker常用命令**:
```bash
docker compose up -d          # 后台启动
docker compose down           # 停止并删除容器
docker compose restart        # 重启服务
docker compose logs -f        # 查看实时日志
docker compose build          # 重新构建镜像
```

---

### ✅ 验证安装

启动所有服务后，验证是否正常运行：

**1. 检查后端健康状态**:
```bash
curl http://localhost:8000/health
# 预期输出: {"status":"healthy"}
```

**2. 访问前端页面**:
打开浏览器访问 http://localhost:3000

**3. 测试Redis连接**:
```bash
redis-cli ping
# 预期输出: PONG
```

**4. 查看API文档**:
访问 http://localhost:8000/docs 查看交互式API文档

---

### 🔍 常见问题

<details>
<summary><b>Q1: Redis连接失败？</b></summary>

**错误**: `ConnectionRefusedError: [Errno 61] Connection refused`

**解决**:
```bash
# 检查Redis是否运行
redis-cli ping

# 如果未运行，启动Redis
docker start xiaoyi-redis
# 或
brew services start redis
```
</details>

<details>
<summary><b>Q2: 前端环境变量undefined？</b></summary>

**原因**: Next.js只能读取 `frontend/.env.local` 文件

**解决**:
```bash
# 确保创建了前端环境变量文件
cp frontend/.env.local.example frontend/.env.local

# 重启前端服务
cd frontend
pnpm dev
```
</details>

<details>
<summary><b>Q3: Python依赖安装失败？</b></summary>

**解决**:
```bash
# 使用uv（速度更快）
uv sync

# 或清理缓存后重装
pip cache purge
pip install -r requirements.txt
```
</details>

<details>
<summary><b>Q4: 端口被占用？</b></summary>

**修改端口**:
```bash
# 后端（修改 .env）
PORT=8001

# 前端（修改启动命令）
pnpm dev -- -p 3001
```
</details>

---

### 📊 服务端口说明

| 服务 | 开发环境 | Docker环境 |
|------|---------|-----------|
| 前端 | 3000 | 13000 |
| 后端API | 8000 | 18000 |
| Redis | 6379 | 6379 |
| MongoDB | 27017 | 27017 |

---

## 📂 项目结构

```
xiaoyi/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── agents/          # AI智能体(事件总结、建议生成等)
│   │   ├── api/             # API路由定义
│   │   │   ├── v1/          # V1版本API
│   │   │   └── v2/          # V2版本API (含用户管理)
│   │   ├── core/            # 核心配置(Config, Auth, Redis)
│   │   ├── data/            # 数据获取与处理
│   │   ├── models/          # 数据模型定义
│   │   └── services/        # 业务逻辑服务
│   ├── pyproject.toml       # Python依赖配置
│   └── Dockerfile           # Docker构建文件
│
├── frontend/                # 前端应用
│   ├── app/                 # Next.js App Router
│   │   ├── api/             # API路由(认证等)
│   │   └── page.tsx         # 主页面
│   ├── components/          # React组件
│   │   ├── chat/            # 聊天组件
│   │   ├── charts/          # 图表组件
│   │   ├── modals/          # 模态框组件
│   │   └── sidebar/         # 侧边栏组件
│   ├── context/             # React Context(认证等)
│   ├── hooks/               # 自定义Hooks
│   ├── lib/                 # 工具库
│   └── public/              # 静态资源
│
└── README.md                # 本文件
```

---

## 🎨 产品体验

### 即聊、即猜、即看

通过自然语言描述需求，系统即时返回序列分析结果。无需复杂配置，输入即得预测。

**核心功能**：

#### 1. 🗣️ 自然语言交互
- **零门槛输入**：无需掌握专业术语，使用日常语言描述分析需求
- **流式实时响应**：采用SSE技术，逐字输出分析结果，体验流畅
- **多轮对话支持**：系统理解上下文，支持追问和深入分析

#### 2. 📈 智能时序可视化
- **动态K线图表**：实时渲染时序数据，支持缩放和交互
- **异常点检测标注**：自动识别并高亮显示关键事件点
- **预测区间可视化**：置信区间以半透明区域展示，直观理解不确定性
- **语义区间切分**：自动将时间轴划分为具有语义含义的阶段

#### 3. 🔐 企业级认证系统
- **Authing IDaaS集成**：基于OAuth 2.0 / OIDC标准协议
- **多种登录方式**：支持邮箱、手机号、社交账号登录
- **用户资料管理**：在线编辑昵称、个人简介、密码
- **会话安全保障**：HttpOnly Cookie + 访问令牌双重保护

#### 4. 💬 会话管理系统
- **多会话并行**：支持创建多个独立分析会话
- **会话历史持久化**：所有对话自动保存至MongoDB
- **会话重命名**：根据分析主题自定义会话标题
- **快速切换**：侧边栏一键切换不同会话

---

## 🔧 配置说明

### 后端环境变量 (.env)

```bash
# LLM配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 数据库配置
MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379

# Authing认证配置
AUTHING_APP_ID=your_app_id
AUTHING_APP_SECRET=your_app_secret
AUTHING_ISSUER=https://your-domain.authing.cn/oidc

# 服务配置
BACKEND_PORT=8000
LOG_LEVEL=INFO
```

### 前端环境变量 (.env.local)

```bash
# 后端API地址
NEXT_PUBLIC_API_URL=http://localhost:8000

# Authing配置
NEXT_PUBLIC_AUTHING_APP_ID=your_app_id
NEXT_PUBLIC_AUTHING_DOMAIN=https://your-domain.authing.cn
```

---

## 📊 性能特性

- **流式响应**: SSE技术实现秒级响应
- **智能缓存**: Redis缓存策略减少重复计算
- **异步处理**: 后台任务异步执行，提升用户体验
- **高性能依赖**: 使用uv进行极速依赖管理

---

## 🛠️ 开发指南

### 代码规范

- **Python**: 遵循PEP 8规范
- **TypeScript**: 使用ESLint + Prettier
- **提交信息**: 遵循Conventional Commits规范

### 本地调试

```bash
# 后端单元测试
cd backend
pytest

# 前端类型检查
cd frontend
pnpm type-check

# 代码格式化
pnpm format
```

---

## 🤝 研究团队

**Beihang University (BUAA)**  
ACT实验室 · SCAL小组

**指导老师**:
- 周号益 (Haoyi Zhou)
- 陈天宇 (Tianyu Chen)

**团队成员**:
- 赵大为 (Dawei Zhao)
- 杨凯伟 (Kaiwei Yang)
- 罗智阳 (Zhiyang Luo)

---

## 📄 学术背景

### Informer：开启长序列时序预测新纪元

本项目技术基础源于 **AAAI 2021 最佳论文** —— **[Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting](https://arxiv.org/abs/2012.07436)**。

**核心贡献**：
- **ProbSparse Self-Attention机制**：将Transformer的时间复杂度从 O(L²) 降低至 O(L log L)
- **Self-Attention Distilling**：通过卷积式蒸馏操作减少内存占用
- **生成式解码器**：一次性预测长序列，避免累积误差

**项目愿景**：
Xiaoyi Guess在Informer的基础上，融合大语言模型的语义理解能力，将专业时序分析推向**可解释AI**的新高度。不仅能"预测准确"，更能"解释清楚"，实现时序分析从专家工具到大众应用的跨越。

---

## 📝 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 📌 项目定位

**Xiaoyi Guess** 致力于打造下一代智能时序分析工具：
- 🎯 **学术研究**：探索LLM与时序模型的协同范式
- 🏢 **工业应用**：降低时序分析门槛，赋能业务决策
- 🌍 **开源贡献**：推动可解释AI在时序领域的普及

---

<div align="center">

**⭐ 如果这个项目对你有帮助，欢迎 Star 支持！**

**让时序预测不再是专家的特权，而是人人可用的工具**

Made with ❤️ by BUAA ACT Lab & SCAL Group

*Powered by Informer × DeepSeek × LangChain*

</div>
