#!/usr/bin/env python3
"""
初始化股票集合脚本
==================

从 AkShare 加载 A 股股票列表并索引到 Qdrant

用法:
    cd backend
    python scripts/init_stock_collection.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.stock_matcher import get_stock_matcher


def main():
    print("=" * 50)
    print("股票集合初始化工具")
    print("=" * 50)

    matcher = get_stock_matcher()

    # 检查是否已有数据
    count = matcher.get_stock_count()
    if count > 0:
        print(f"\n✅ 股票集合已有 {count} 条记录")
        response = input("是否重新初始化? (y/N): ").strip().lower()
        if response != 'y':
            print("取消初始化")
            return

        # 删除现有集合
        try:
            matcher.client.delete_collection(matcher.collection_name)
            print(f"🗑️ 已删除现有集合: {matcher.collection_name}")
        except Exception as e:
            print(f"删除集合失败: {e}")

    # 从 AkShare 加载股票列表
    print("\n📊 从 AkShare 加载 A 股股票列表...")
    records = matcher.load_stocks_from_akshare()

    if not records:
        print("❌ 加载股票列表失败")
        return

    print(f"✅ 加载了 {len(records)} 只股票")

    # 索引到 Qdrant
    print("\n📥 索引股票数据到 Qdrant...")
    matcher.index_stocks(records, batch_size=100)

    # 验证
    final_count = matcher.get_stock_count()
    print(f"\n✅ 初始化完成！共 {final_count} 条记录")

    # 测试匹配
    print("\n🧪 测试股票匹配:")
    test_queries = ["茅台", "比亚迪", "宁德", "600519"]
    for query in test_queries:
        result = matcher.match(query)
        if result.success and result.stock_info:
            print(f"  '{query}' → {result.stock_info.stock_name}({result.stock_info.stock_code}) [置信度: {result.confidence:.2f}]")
        else:
            print(f"  '{query}' → {result.error_message}")


if __name__ == "__main__":
    main()
