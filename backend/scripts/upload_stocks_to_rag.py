"""
上传股票信息到外部 RAG 服务
===========================

从 AkShare 获取 A 股股票列表，上传到外部 RAG 服务

用法:
    python -m scripts.upload_stocks_to_rag
"""

import os
import httpx
import akshare as ak
from typing import List, Dict

# RAG 服务地址
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://10.139.197.44:8000")


def get_stocks_from_akshare() -> List[Dict]:
    """从 AkShare 获取 A 股股票列表"""
    print("[Upload] 从 AkShare 获取股票列表...")

    df = ak.stock_info_a_code_name()
    stocks = []

    for _, row in df.iterrows():
        code = row["code"]
        name = row["name"]

        # 判断市场
        if code.startswith("6"):
            market = "SH"
        elif code.startswith(("0", "3")):
            market = "SZ"
        else:
            market = "SZ"

        stocks.append({
            "stock_code": code,
            "stock_name": name,
            "market": market,
            "status": "listed"
        })

    print(f"[Upload] 获取了 {len(stocks)} 只股票")
    return stocks


def upload_stock_to_rag(stock: Dict, client: httpx.Client) -> bool:
    """上传单个股票到 RAG 服务"""
    # 构建文档内容 - 只用官方名称，不需要别名
    content = f"""股票名称: {stock['stock_name']}
股票代码: {stock['stock_code']}
市场: {stock['market']}
状态: {stock['status']}
"""

    try:
        # 创建文件对象
        files = {
            "file": (
                f"stock_{stock['stock_code']}.txt",
                content.encode("utf-8"),
                "text/plain"
            )
        }

        # 元数据
        data = {
            "title": f"{stock['stock_name']} ({stock['stock_code']})",
            "metadata": str({
                "type": "stock_info",
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "market": stock["market"]
            })
        }

        response = client.post(
            f"{RAG_SERVICE_URL}/api/v1/documents",
            files=files,
            data=data,
            timeout=30.0
        )
        response.raise_for_status()
        return True

    except Exception as e:
        print(f"[Upload] 上传失败 {stock['stock_code']}: {e}")
        return False


def upload_stocks_batch(stocks: List[Dict], batch_size: int = 100):
    """批量上传股票"""
    print(f"[Upload] 开始上传 {len(stocks)} 只股票...")

    success_count = 0
    fail_count = 0

    with httpx.Client() as client:
        for i, stock in enumerate(stocks):
            if upload_stock_to_rag(stock, client):
                success_count += 1
            else:
                fail_count += 1

            # 进度显示
            if (i + 1) % batch_size == 0:
                print(f"[Upload] 进度: {i + 1}/{len(stocks)}, 成功: {success_count}, 失败: {fail_count}")

    print(f"[Upload] 完成! 成功: {success_count}, 失败: {fail_count}")


def check_rag_service():
    """检查 RAG 服务是否可用"""
    try:
        response = httpx.get(f"{RAG_SERVICE_URL}/api/v1/health", timeout=10.0)
        if response.status_code == 200:
            print(f"[Upload] RAG 服务可用: {RAG_SERVICE_URL}")
            return True
        else:
            print(f"[Upload] RAG 服务返回: {response.status_code}")
            return False
    except Exception as e:
        print(f"[Upload] RAG 服务不可用: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("股票信息上传到 RAG 服务")
    print("=" * 50)

    # 检查 RAG 服务
    if not check_rag_service():
        print("[Upload] 请确保 RAG 服务正在运行")
        return

    # 获取股票列表
    stocks = get_stocks_from_akshare()

    # 上传
    upload_stocks_batch(stocks)


if __name__ == "__main__":
    main()
