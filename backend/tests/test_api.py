"""FastAPI 端点测试"""
import json


def test_root(client):
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "小易猜猜 API", "version": "1.0.0"}


def test_health(client):
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_stream_invalid_model(client):
    """测试无效模型 - 应返回 error 类型"""
    response = client.post(
        "/api/chat/stream",
        json={"message": "帮我分析一下平安银行的股价走势", "model": "invalid_model"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # 解析 SSE 消息
    first_msg = response.text.split("\n\n")[0]
    assert first_msg.startswith("data: ")
    data = json.loads(first_msg[6:])

    # 预期返回 error 类型
    assert data == {
        "type": "error",
        "message": "不支持的模型: invalid_model。支持: 'prophet', 'xgboost', 'randomforest', 'dlinear'"
    }


def test_chat_stream_prophet(client):
    """测试 Prophet 模型分析"""
    response = client.post(
        "/api/chat/stream",
        json={"message": "帮我预测一下贵州茅台未来30天的股价", "model": "prophet"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # 验证至少有一条消息
    messages = [m for m in response.text.split("\n\n") if m.strip()]
    assert len(messages) > 0

    # 验证每条消息格式
    for msg in messages:
        assert msg.startswith("data: ")
        data = json.loads(msg[6:])
        assert "type" in data
        assert data["type"] in ["error", "session", "step", "content"]


def test_chat_stream_xgboost(client):
    """测试 XGBoost 模型分析"""
    response = client.post(
        "/api/chat/stream",
        json={"message": "用XGBoost分析沪深300指数走势", "model": "xgboost"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    messages = [m for m in response.text.split("\n\n") if m.strip()]
    assert len(messages) > 0

    for msg in messages:
        assert msg.startswith("data: ")
        data = json.loads(msg[6:])
        assert "type" in data
