# FastAPI 后端对接文档

## 概述

本文档描述了前端（Next.js）与后端（FastAPI）进行时间序列预测对话的API接口规范。前端使用 **Server-Sent Events (SSE)** 流式响应来实时接收步骤状态更新和消息内容。

## 业务流程

1. **用户提问**：用户使用自然语言提问（如"帮我分析一下茅台，预测下个季度走势"）
2. **获取时序数据**：后端根据用户问题，从 akshare 数据库获取相关的时序数据
3. **展示时序数据**：后端先将时序数据以表格或图表形式发送给前端展示
4. **执行预测步骤**：后端将时序数据交给 TimeCopilot 进行处理，执行7个预测步骤
5. **返回分析结果**：后端将 TimeCopilot 返回的 JSON 结果转换为前端可展示的格式（文本、表格、图表）

**重要：时序数据必须在步骤开始前发送，让用户先看到原始数据。**

---

## 接口规范

### 1. 对话流式接口

**接口地址：** `POST /api/chat/stream`

**请求头：**
```
Content-Type: application/json
```

**请求体：**
```json
{
  "message": "帮我分析一下茅台，预测下个季度走势，结合最新的研报观点"
}
```

**响应格式：** Server-Sent Events (SSE) 流式响应

**响应头：**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

---

## 响应数据格式

后端需要以 SSE 格式发送数据，每行以 `data: ` 开头，后跟 JSON 字符串。

## 响应流程

完整的响应流程如下：

1. **时序数据展示**（可选，但推荐）：在步骤开始前，先发送从 akshare 获取的时序数据
2. **步骤状态更新**：依次执行7个预测步骤，实时更新步骤状态
3. **分析结果内容**：步骤完成后，发送分析结果（文本、表格、图表等）

---

### 1. 时序数据展示（响应开始）

在开始执行预测步骤之前，后端应该先发送从 akshare 获取的时序数据。这可以让用户先看到原始数据，然后再看到分析结果。

**发送时机：** 在步骤状态更新之前

**格式：**
```
data: {"type": "content", "content": {...}}
```

**时序数据展示方式：**

#### 方式一：表格形式（推荐用于展示原始数据）

```json
{
  "type": "content",
  "content": {
    "type": "table",
    "title": "历史时序数据",
    "headers": ["日期", "开盘价", "收盘价", "最高价", "最低价", "成交量"],
    "rows": [
      ["2024-01-01", 1850.00, 1860.50, 1870.00, 1845.00, 1234567],
      ["2024-01-02", 1860.50, 1875.20, 1880.00, 1858.00, 1456789],
      ["2024-01-03", 1875.20, 1865.80, 1885.00, 1860.00, 1345678]
    ]
  }
}
```

#### 方式二：图表形式（推荐用于展示趋势）

```json
{
  "type": "content",
  "content": {
    "type": "chart",
    "title": "历史价格趋势",
    "data": {
      "labels": ["2024-01-01", "2024-01-02", "2024-01-03", ...],
      "datasets": [
        {
          "label": "收盘价",
          "data": [1860.50, 1875.20, 1865.80, ...],
          "color": "#8b5cf6"
        }
      ]
    }
  }
}
```

**建议：**
- 如果数据量较小（< 100行），可以同时发送表格和图表
- 如果数据量较大，建议只发送图表，或者表格只显示最近N条数据

**示例：**

```json
// 先发送表格（最近20条数据）
{
  "type": "content",
  "content": {
    "type": "table",
    "title": "历史时序数据（最近20条）",
    "headers": ["日期", "收盘价", "成交量"],
    "rows": [
      ["2024-12-01", 1850.00, 1234567],
      ["2024-12-02", 1860.50, 1456789],
      ...
    ]
  }
}

// 再发送图表（完整数据趋势）
{
  "type": "content",
  "content": {
    "type": "chart",
    "title": "历史价格趋势（365天）",
    "data": {
      "labels": ["2024-01-01", "2024-01-02", ...],
      "datasets": [
        {
          "label": "收盘价",
          "data": [1850.00, 1860.50, ...],
          "color": "#8b5cf6"
        }
      ]
    }
  }
}
```

---

### 2. 步骤状态更新

当预测步骤状态发生变化时，发送步骤更新消息。

**格式：**
```
data: {"type": "step", "steps": [...]}
```

**步骤数据结构：**

```typescript
interface Step {
  id: string        // 步骤ID，固定值：'1', '2', '3', '4', '5', '6', '7'
  name: string     // 步骤名称
  status: 'pending' | 'running' | 'completed' | 'failed'  // 步骤状态
  message?: string  // 步骤完成消息（可选）
}
```

**步骤定义（7个固定步骤）：**

| ID | 步骤名称 | 说明 |
|---|---|---|
| 1 | 数据获取与预处理 | 获取股票历史数据并进行清洗 |
| 2 | 时序特征分析 | 分析趋势强度、季节性、波动性等 |
| 3 | 异常检测 | 识别历史数据中的异常波动点 |
| 4 | 模型训练与评估 | 训练多个模型并评估性能 |
| 5 | 预测生成 | 使用最优模型生成未来预测值 |
| 6 | 结果可视化 | 生成预测图表 |
| 7 | 分析完成 | 整合结果并生成报告 |

**示例：**

```json
{
  "type": "step",
  "steps": [
    {
      "id": "1",
      "name": "数据获取与预处理",
      "status": "running",
      "message": "处理中..."
    },
    {
      "id": "2",
      "name": "时序特征分析",
      "status": "pending"
    },
    {
      "id": "3",
      "name": "异常检测",
      "status": "pending"
    },
    {
      "id": "4",
      "name": "模型训练与评估",
      "status": "pending"
    },
    {
      "id": "5",
      "name": "预测生成",
      "status": "pending"
    },
    {
      "id": "6",
      "name": "结果可视化",
      "status": "pending"
    },
    {
      "id": "7",
      "name": "分析完成",
      "status": "pending"
    }
  ]
}
```

**步骤状态更新流程：**

1. 当步骤开始时，将该步骤的 `status` 设置为 `"running"`，并发送更新
2. 当步骤完成时，将该步骤的 `status` 设置为 `"completed"`，并设置 `message` 字段，发送更新
3. 如果步骤失败，将 `status` 设置为 `"failed"`，并设置错误消息

---

### 2. 消息内容

当步骤完成后，发送消息内容。一条完整的回答可能包含多个内容块（文本、表格、图表等）。

**格式：**
```
data: {"type": "content", "content": {...}}
```

**内容类型：**

#### 2.1 文本内容 (text)

```typescript
{
  "type": "text",
  "text": "好的！我已经完成了对 **600519.SH 贵州茅台** 的分析。以下是详细结果："
}
```

**说明：**
- `text` 字段支持 Markdown 格式
- 支持加粗 `**text**`、列表、代码块等

**示例：**
```json
{
  "type": "content",
  "content": {
    "type": "text",
    "text": "**预测结论：**\n\n根据 AutoARIMA 模型分析，预计下个季度贵州茅台股价将**上涨 8.5%**，目标价位在 **¥1920 - ¥2050** 区间。"
  }
}
```

#### 2.2 表格内容 (table)

```typescript
{
  "type": "table",
  "title": "模型性能对比",  // 可选
  "headers": ["模型", "MASE", "MAE", "RMSE"],
  "rows": [
    ["AutoARIMA", 0.82, 45.2, 58.3],
    ["Prophet", 0.91, 50.1, 64.5],
    ["Chronos", 0.95, 52.8, 67.2],
    ["SeasonalNaive", 1.00, 55.6, 71.4]
  ]
}
```

**说明：**
- `headers` 数组定义表格列头
- `rows` 数组的每个元素是一行数据，元素数量需与 `headers` 长度一致
- 单元格值可以是字符串或数字

**示例：**
```json
{
  "type": "content",
  "content": {
    "type": "table",
    "title": "模型性能对比",
    "headers": ["模型", "MASE", "MAE", "RMSE"],
    "rows": [
      ["AutoARIMA", 0.82, 45.2, 58.3],
      ["Prophet", 0.91, 50.1, 64.5]
    ]
  }
}
```

#### 2.3 图表内容 (chart)

```typescript
{
  "type": "chart",
  "title": "价格预测趋势图",  // 可选
  "data": {
    "labels": ["01-01", "01-02", "01-03", ...],  // X轴标签（日期）
    "datasets": [
      {
        "label": "历史价格",
        "data": [1850, 1860, 1845, ...],  // 数据数组，长度需与labels一致
        "color": "#8b5cf6"  // 可选，线条颜色（十六进制）
      },
      {
        "label": "预测价格",
        "data": [null, null, ..., 1920, 1950, ...],  // 可以使用null表示不显示该点
        "color": "#06b6d4"
      }
    ]
  },
  "chartType": "line"  // 可选，默认 "line"，支持 "line" | "bar" | "area"
}
```

**说明：**
- `labels` 数组是 X 轴标签（通常是日期）
- `datasets` 数组可以包含多个数据集（多条线）
- 每个数据集的 `data` 数组长度必须与 `labels` 长度一致
- 使用 `null` 值可以隐藏某些数据点（例如：历史数据只在历史部分显示，预测数据只在预测部分显示）

**示例：**
```json
{
  "type": "content",
  "content": {
    "type": "chart",
    "title": "价格预测趋势图",
    "data": {
      "labels": ["12-01", "12-02", "12-03", "01-01", "01-02", "01-03"],
      "datasets": [
        {
          "label": "历史价格",
          "data": [1850, 1860, 1845, null, null, null],
          "color": "#8b5cf6"
        },
        {
          "label": "预测价格",
          "data": [null, null, null, 1920, 1950, 1980],
          "color": "#06b6d4"
        }
      ]
    }
  }
}
```

---

## 完整响应流程示例

以下是一个完整的响应流程示例（包含时序数据展示）：

```
// 1. 首先发送时序数据（从 akshare 获取）
data: {"type": "content", "content": {"type": "table", "title": "历史时序数据（最近20条）", "headers": ["日期", "收盘价", "成交量"], "rows": [...]}}

data: {"type": "content", "content": {"type": "chart", "title": "历史价格趋势（365天）", "data": {...}}}

// 2. 开始执行预测步骤
data: {"type": "step", "steps": [{"id": "1", "name": "数据获取与预处理", "status": "running", "message": "处理中..."}, ...]}

data: {"type": "step", "steps": [{"id": "1", "name": "数据获取与预处理", "status": "completed", "message": "已获取历史数据 365 天"}, ...]}

data: {"type": "step", "steps": [{"id": "2", "name": "时序特征分析", "status": "running", "message": "处理中..."}, ...]}

data: {"type": "step", "steps": [{"id": "2", "name": "时序特征分析", "status": "completed", "message": "趋势强度: 0.78, 季节性: 0.32"}, ...]}

... (继续其他步骤)

// 3. 步骤完成后，发送分析结果
data: {"type": "content", "content": {"type": "text", "text": "好的！我已经完成了对 **600519.SH 贵州茅台** 的分析。"}}

data: {"type": "content", "content": {"type": "table", "title": "模型性能对比", "headers": [...], "rows": [...]}}

data: {"type": "content", "content": {"type": "chart", "title": "价格预测趋势图", "data": {...}}}

data: {"type": "content", "content": {"type": "text", "text": "**预测结论：**\n\n..."}}
```

---

## 错误处理

如果处理过程中发生错误，可以发送错误消息：

**格式：**
```
data: {"type": "error", "message": "错误描述信息"}
```

或者将步骤状态设置为 `"failed"`：

```json
{
  "type": "step",
  "steps": [
    {
      "id": "4",
      "name": "模型训练与评估",
      "status": "failed",
      "message": "模型训练失败：数据不足"
    }
  ]
}
```

---

## FastAPI 实现示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        # ========== 第一步：发送时序数据（从 akshare 获取） ==========
        # 1.1 发送表格（最近20条数据）
        import akshare as ak
        # 假设从 akshare 获取数据
        # df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20240101", end_date="20241231")
        
        # 转换为表格格式（示例）
        table_content = {
            "type": "content",
            "content": {
                "type": "table",
                "title": "历史时序数据（最近20条）",
                "headers": ["日期", "收盘价", "成交量"],
                "rows": [
                    # 从 akshare 数据转换而来
                    ["2024-12-01", 1850.00, 1234567],
                    ["2024-12-02", 1860.50, 1456789],
                    # ... 更多数据
                ]
            }
        }
        yield f"data: {json.dumps(table_content)}\n\n"
        
        # 1.2 发送图表（完整数据趋势）
        chart_content = {
            "type": "content",
            "content": {
                "type": "chart",
                "title": "历史价格趋势",
                "data": {
                    "labels": ["2024-01-01", "2024-01-02", ...],  # 从 akshare 数据获取
                    "datasets": [
                        {
                            "label": "收盘价",
                            "data": [1850.00, 1860.50, ...],  # 从 akshare 数据获取
                            "color": "#8b5cf6"
                        }
                    ]
                }
            }
        }
        yield f"data: {json.dumps(chart_content)}\n\n"
        
        # ========== 第二步：初始化步骤并开始执行 ==========
        steps = [
            {"id": "1", "name": "数据获取与预处理", "status": "pending"},
            {"id": "2", "name": "时序特征分析", "status": "pending"},
            {"id": "3", "name": "异常检测", "status": "pending"},
            {"id": "4", "name": "模型训练与评估", "status": "pending"},
            {"id": "5", "name": "预测生成", "status": "pending"},
            {"id": "6", "name": "结果可视化", "status": "pending"},
            {"id": "7", "name": "分析完成", "status": "pending"},
        ]
        
        # 执行步骤1
        steps[0]["status"] = "running"
        steps[0]["message"] = "处理中..."
        yield f"data: {json.dumps({'type': 'step', 'steps': steps})}\n\n"
        await asyncio.sleep(1)  # 模拟处理时间
        
        steps[0]["status"] = "completed"
        steps[0]["message"] = "已获取历史数据 365 天"
        yield f"data: {json.dumps({'type': 'step', 'steps': steps})}\n\n"
        
        # ... 继续其他步骤
        
        # ========== 第三步：步骤完成后，发送分析结果 ==========
        # 发送文本内容
        text_content = {
            "type": "content",
            "content": {
                "type": "text",
                "text": "好的！我已经完成了分析。"
            }
        }
        yield f"data: {json.dumps(text_content)}\n\n"
        
        # 发送表格内容
        table_content = {
            "type": "content",
            "content": {
                "type": "table",
                "title": "模型性能对比",
                "headers": ["模型", "MASE", "MAE"],
                "rows": [
                    ["AutoARIMA", 0.82, 45.2],
                    ["Prophet", 0.91, 50.1]
                ]
            }
        }
        yield f"data: {json.dumps(table_content)}\n\n"
        
        # 发送图表内容
        chart_content = {
            "type": "content",
            "content": {
                "type": "chart",
                "title": "价格预测趋势图",
                "data": {
                    "labels": ["01-01", "01-02", "01-03"],
                    "datasets": [
                        {
                            "label": "历史价格",
                            "data": [1850, 1860, 1845],
                            "color": "#8b5cf6"
                        }
                    ]
                }
            }
        }
        yield f"data: {json.dumps(chart_content)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

---

## 注意事项

1. **响应顺序**：
   - **必须先发送时序数据**（表格或图表），然后再开始步骤流程
   - 时序数据应该在步骤状态更新之前发送
   - 这样用户可以立即看到原始数据，然后再看到分析过程

2. **SSE 格式要求**：
   - 每行必须以 `data: ` 开头
   - 每行末尾需要 `\n\n`（两个换行符）
   - JSON 数据需要正确转义

3. **步骤更新**：
   - 每次步骤状态变化都需要发送完整的步骤数组
   - 前端会根据步骤ID更新对应步骤的状态

4. **内容顺序**：
   - 时序数据 → 步骤更新 → 分析结果内容
   - 前端会按接收顺序显示

5. **性能优化**：
   - 建议在步骤完成后立即发送对应的内容
   - 避免在最后一次性发送所有内容
   - 时序数据如果很大，可以只发送最近N条或只发送图表

6. **CORS 配置**：
   - 确保后端配置了正确的 CORS 头，允许前端域名访问

7. **时序数据来源**：
   - 从 akshare 获取的时序数据应该转换为表格或图表格式
   - 建议同时提供表格（最近数据）和图表（完整趋势）

---

## 测试建议

1. 使用 Postman 或 curl 测试 SSE 接口
2. 确保响应格式符合 SSE 规范
3. 测试各种错误场景（网络错误、处理失败等）
4. 验证步骤状态更新的实时性

---

## 联系方式

如有问题，请联系前端开发团队。

