# 🔮 小易猜猜 (XiaoYi GuessGuess)

> 人机友好的时间序列预测助手，基于 TimeCopilot 构建

## 🚀 快速开始

### 方式一：Dev Container (推荐)

1. 安装 [VS Code](https://code.visualstudio.com/) 和 [Docker Desktop](https://www.docker.com/products/docker-desktop)
2. 安装 VS Code 扩展：[Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
3. 打开项目，按 `F1` 输入 `Dev Containers: Reopen in Container`
4. 等待容器构建完成（首次约 3-5 分钟）

### 方式二：本地开发

```bash
# 前置要求
# - Node.js 20+
# - Python 3.11+
# - PostgreSQL 16 (带 pgvector 扩展)

# 安装前端依赖
cd apps/web
pnpm install

# 启动前端
pnpm dev
```

## 📁 项目结构

```
xiaoyi-cai/
├── .devcontainer/        # Dev Container 配置
│   ├── devcontainer.json
│   ├── docker-compose.yml
│   └── Dockerfile
├── apps/
│   ├── web/              # 🎨 前端 (Next.js 14)
│   │   ├── app/          # 页面
│   │   ├── components/   # 组件
│   │   │   ├── chat/     # 对话相关组件
│   │   │   ├── layout/   # 布局组件
│   │   │   ├── charts/   # 图表组件 (TODO)
│   │   │   └── ui/       # 基础UI组件 (TODO)
│   │   ├── hooks/        # 自定义 Hooks
│   │   └── lib/          # 工具函数
│   └── api/              # 🔧 后端 (FastAPI) - TODO
└── docs/                 # 📚 文档
```

## 🎯 新手任务

### Easy (1-2小时)
- [ ] `#001` 创建 `Button` 组件 (`components/ui/Button.tsx`)
- [ ] `#002` 创建 `Card` 组件 (`components/ui/Card.tsx`)
- [ ] `#003` 创建 `Modal` 组件 (`components/ui/Modal.tsx`)
- [ ] `#004` 创建 `Input` 组件 (`components/ui/Input.tsx`)

### Medium (3-5小时)
- [ ] `#101` 完善 `MessageBubble` 支持完整 Markdown
- [ ] `#102` 实现 `ForecastChart` 预测图表组件
- [ ] `#103` 实现对话历史持久化 (localStorage)
- [ ] `#104` 实现数据上传弹窗

### Hard (1天+)
- [ ] `#201` WebSocket 实时对话
- [ ] `#202` 接入真实股票数据 (AKShare)

## 🔧 技术栈

- **前端**: Next.js 14, React 18, Tailwind CSS, Recharts
- **后端**: FastAPI, Python 3.11
- **数据库**: PostgreSQL 16 + pgvector
- **数据源**: AKShare, Baostock

## 📝 开发规范

### 分支命名
- `feat/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档

### 提交信息
- `feat: 添加xxx功能`
- `fix: 修复xxx问题`
- `docs: 更新xxx文档`

## 🔗 相关链接

- [TimeCopilot 文档](https://nixtla.mintlify.app/timecopilot)
- [Next.js 文档](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [AKShare 文档](https://akshare.akfamily.xyz/)

test