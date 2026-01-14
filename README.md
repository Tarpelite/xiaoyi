# 🔮 小易猜猜 (XiaoYi)

> 基于 AI 的智能金融分析与预测平台

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 核心特性

### 🤖 智能分析
- **自然语言交互**: 使用自然语言描述需求，AI 自动解析并执行分析
- **多模型预测**: 支持 Prophet、XGBoost、RandomForest、DLinear 四种预测模型
- **深度报告**: AI 生成 600-800 字专业分析报告，包含投资建议和风险提示
- **🆕 交互式回测**: 拖动滑块选择历史分割点，实时验证模型准确性

### 📊 数据分析
- **时序预测**: 基于历史数据预测未来走势（动态horizon: max(90天, 今天)）
- **市场情绪**: 综合新闻和技术指标分析市场情绪（-1 到 1）
- **新闻集成**: 自动获取相关新闻并进行AI总结
- **研报集成**: 支持研报检索和总结（可扩展）

### 🎨 现代化界面
- **异步渲染**: 基于 Redis 的会话管理，实时展示 7 个分析步骤
- **专业图表**: Recharts 动态展示历史数据和预测走势
- **🆕 回测可视化**: 三线对比（历史/实际/预测）+ MAE指标显示
- **情绪仪表盘**: 汽车仪表盘样式的市场情绪可视化
- **Markdown 报告**: 结构化、专业的分析报告展示

### 🏗️ 技术架构
- **前后端分离**: Next.js + FastAPI
- **会话管理**: Redis 缓存，24 小时 TTL
- **异步任务**: 后台任务处理，前端轮询获取进度
- **类型安全**: Pydantic 数据验证
- **🆕 实时回测**: 防抖 + AbortController 处理竞态条件

## 📁 项目结构

```
xiaoyi/
├── backend/                # 🔧 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/            # API 路由层
│   │   │   └── v2/endpoints/
│   │   │       ├── unified_analysis.py  # 统一分析端点 ✨
│   │   │       └── backtest.py          # 回测端点 🆕
│   │   ├── core/           # 核心模块
│   │   │   ├── config.py        # 配置管理
│   │   │   ├── redis_client.py  # Redis 客户端 ✨
│   │   │   ├── session.py       # Session 管理 ✨
│   │   │   └── unified_tasks.py # 异步任务处理 ✨
│   │   ├── schemas/        # 数据模型
│   │   │   └── session_schema.py # Session Pydantic 模型 🆕
│   │   ├── agents/         # Agent 层
│   │   │   ├── nlp_agent.py     # NLP 解析
│   │   │   ├── report_agent.py  # 报告生成（增强）✨
│   │   │   └── feature_agents.py # 新闻/情绪分析 ✨
│   │   ├── models/         # 预测模型层
│   │   │   ├── base.py          # 基础接口
│   │   │   ├── analyzer.py      # 特征分析
│   │   │   ├── prophet.py       # Prophet
│   │   │   ├── xgboost.py       # XGBoost
│   │   │   ├── randomforest.py  # RandomForest
│   │   │   └── dlinear.py       # DLinear（完整实现 + 修复）🆕
│   │   ├── data/           # 数据层
│   │   │   └── fetcher.py       # 数据获取
│   │   └── main.py         # 应用入口
│   ├── requirements.txt    # Python 依赖
│   ├── .env               # 环境变量
│   └── .env.example       # 环境变量模板
│
├── frontend/               # 🎨 前端应用 (Next.js)
│   ├── app/
│   │   └── analysis/       # 分析页面 ✨
│   │       └── page.tsx
│   ├── hooks/
│   │   └── useBacktestSimulation.ts # 回测Hook 🆕
│   ├── lib/api/
│   │   └── analysis.ts    # 分析API客户端 ✨
│   └── components/
│       └── chat/
│           ├── ChatArea.tsx           # 聊天主界面 ✨
│           ├── MessageContent.tsx     # 消息内容（含图表）🆕
│           └── BacktestControls.tsx   # 回测控制组件 🆕
│
├── docker-compose.yml     # Docker 配置
└── README.md
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Redis 7.0+
- pnpm (推荐) 或 npm

### 1. 启动 Redis

```bash
# 使用 Docker Compose
docker-compose up -d redis

# 或直接启动
redis-server
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 DEEPSEEK_API_KEY

# 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm run dev
```

### 4. 访问应用

- **分析页面**: http://localhost:3000 ✨ (推荐)
- **API 文档**: http://localhost:8000/docs


## 📊 Redis Session Schema

### 数据结构

```json
{
  "session_id": "uuid",
  "message_id": "uuid",
  "user_query": "分析贵州茅台",
  "model_name": "prophet",
  
  "status": "completed",
  "steps": 7,
  "total_steps": 7,
  
  "time_series_original": [
    {"date": "2025-01-01", "value": 1856.32, "is_prediction": false}
  ],
  "time_series_full": [
    {"date": "2025-01-01", "value": 1856.32, "is_prediction": false},
    {"date": "2026-01-08", "value": 1923.45, "is_prediction": true}
  ],
  "prediction_done": true,
  "prediction_start_day": "2026-01-07",
  
  "news_list": [...],
  "emotion": 0.7,
  "emotion_des": "市场情绪偏乐观",
  
  "conclusion": "# 综合分析报告...",
  
  "created_at": "2026-01-08T00:00:00",
  "updated_at": "2026-01-08T00:05:00"
}
```

## 🔄 异步分析流程

### 分析步骤

1. **解析需求** 🔍 - NLP 解析用户问题
2. **获取数据** 📊 - 从 AKShare 获取股票数据
3. **特征分析** 📈 - 提取时序特征
4. **获取新闻** 📰 - 获取相关新闻并总结
5. **情绪分析** 😊 - 分析市场情绪
6. **模型预测** 🔮 - 运行预测模型（动态horizon）
7. **生成报告** 📝 - AI 生成专业报告

### API 调用流程

```bash
# 1. 创建分析任务
POST /api/analysis/create
{
  "message": "分析贵州茅台未来走势",
  "model": "prophet"
}
# => { "session_id": "xxx", "message_id": "yyy" }

# 2. 轮询任务状态
GET /api/analysis/status/{session_id}?message_id={message_id}

# 3. (可选) 回测验证
POST /api/analysis/backtest
{
  "session_id": "xxx",
  "message_id": "yyy",
  "split_date": "2025-04-16"
}
# => { "metrics": {...}, "backtest_data": [...], "ground_truth": [...] }
```

## 🎯 预测模型

### Prophet
- Facebook 开源时序预测
- 适合有季节性的数据
- 自动处理异常值

### XGBoost
- 梯度提升树
- 支持特征工程
- 高性能预测

### RandomForest
- 随机森林集成学习
- 稳定性好
- 抗过拟合

### DLinear 🆕
- 论文标准实现
- Series Decomposition（移动平均分解）
- **修复**: 递归预测使用原始值窗口，避免误差累积

## 🔧 配置说明

### 环境变量 (.env)

```env
# API Keys
DEEPSEEK_API_KEY=your_api_key_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Server
HOST=0.0.0.0
PORT=8000
```

## 🛠️ 技术栈

### 后端
- **FastAPI** - 现代化 API 框架
- **Redis** - 会话缓存
- **Pydantic** - 数据验证
- **AKShare** - 金融数据获取
- **DeepSeek AI** - LLM 能力
- **Prophet / XGBoost / RandomForest / DLinear** - 预测模型

### 前端
- **Next.js 14** - React 框架
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式
- **Recharts** - 图表库
- **React Markdown** - Markdown 渲染
- **Lucide React** - 图标库

## 🚧 已完成功能

- [x] 多模型预测（Prophet/XGBoost/RandomForest/DLinear）
- [x] 异步任务处理（Redis Session）
- [x] AI 深度报告生成（600-800字）
- [x] 市场情绪分析（LLM + 规则）
- [x] 新闻集成与总结
- [x] **交互式时间旅行回测** 🆕
- [x] **动态预测Horizon** 🆕
- [x] **DLinear递归预测修复** 🆕

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

- 项目主页: [GitHub Repository]
- 问题反馈: [Issues]
