"""
GDELT 新闻查询脚本
==================

使用 GDELT 2.0 Doc API 查询历史新闻

注意：GDELT 2.0 Doc API 官方只支持最近 3 个月的新闻
如需查询更久的历史数据，需要使用 Google BigQuery

使用方法:
    python gdelt_query.py "茅台" --days 90
    python gdelt_query.py "贵州茅台" --start 2024-10-01 --end 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

try:
    from gdeltdoc import GdeltDoc, Filters

    GDELT_AVAILABLE = True
except ImportError:
    GDELT_AVAILABLE = False
    print("⚠️ gdeltdoc 未安装，请运行: pip install gdeltdoc")


class GDELTNewsClient:
    """GDELT 新闻查询客户端"""

    # GDELT API 限制：最多 3 个月
    MAX_DAYS = 90

    # 中文股票名称到英文的映射
    STOCK_NAME_MAP = {
        "茅台": "Kweichow Moutai",
        "贵州茅台": "Kweichow Moutai",
        "比亚迪": "BYD",
        "宁德时代": "CATL",
        "中石油": "PetroChina",
        "中石化": "Sinopec",
        "工商银行": "ICBC",
        "建设银行": "CCB",
        "招商银行": "CMB China Merchants Bank",
        "平安": "Ping An",
        "腾讯": "Tencent",
        "阿里巴巴": "Alibaba",
        "京东": "JD.com",
        "小米": "Xiaomi",
        "华为": "Huawei",
        "字节跳动": "ByteDance",
        "美团": "Meituan",
        "百度": "Baidu",
        "网易": "NetEase",
    }

    def __init__(self):
        if not GDELT_AVAILABLE:
            raise ImportError("请先安装 gdeltdoc: pip install gdeltdoc")
        self.client = GdeltDoc()

    def _translate_keyword(self, keyword: str) -> str:
        """将中文关键词转换为英文（GDELT 对中文支持较差）"""
        # 先检查映射表
        if keyword in self.STOCK_NAME_MAP:
            translated = self.STOCK_NAME_MAP[keyword]
            print(f"📝 关键词转换: '{keyword}' → '{translated}'")
            return translated

        # 如果关键词太短（少于4个字符），尝试扩展
        if len(keyword) < 4:
            # 对于中文，每个字符算1个，GDELT要求至少4个字符
            expanded = f"{keyword} China stock"
            print(f"📝 关键词扩展: '{keyword}' → '{expanded}'")
            return expanded

        return keyword

    def search(
        self,
        keyword: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
        country: Optional[list] = None,
        domain: Optional[list] = None,
        language: str = "Chinese",
    ) -> pd.DataFrame:
        """
        搜索 GDELT 新闻

        Args:
            keyword: 搜索关键词
            start_date: 开始日期 (YYYY-MM-DD)，默认为 end_date - days
            end_date: 结束日期 (YYYY-MM-DD)，默认为今天
            days: 查询天数（如果未指定 start_date），最大 90 天
            country: 国家过滤，如 ["China"]
            domain: 域名过滤，如 ["sina.com.cn", "eastmoney.com"]
            language: 语言过滤

        Returns:
            新闻 DataFrame
        """
        # 处理日期
        if end_date is None:
            end_dt = datetime.now()
        else:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if start_date is None:
            # 限制最大天数
            actual_days = min(days, self.MAX_DAYS)
            if days > self.MAX_DAYS:
                print(f"⚠️ GDELT API 限制：最多查询 {self.MAX_DAYS} 天，已自动调整")
            start_dt = end_dt - timedelta(days=actual_days)
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            # 检查日期范围
            date_diff = (end_dt - start_dt).days
            if date_diff > self.MAX_DAYS:
                print(f"⚠️ GDELT API 限制：最多查询 {self.MAX_DAYS} 天")
                print(f"   请求范围 {date_diff} 天，将分批查询...")
                return self._batch_search(
                    keyword, start_dt, end_dt, country, domain, language
                )

        return self._single_search(
            keyword,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d"),
            country,
            domain,
            language,
        )

    def _single_search(
        self,
        keyword: str,
        start_date: str,
        end_date: str,
        country: Optional[list] = None,
        domain: Optional[list] = None,
        language: str = "Chinese",
    ) -> pd.DataFrame:
        """执行单次查询"""
        # 转换关键词（处理中文）
        search_keyword = self._translate_keyword(keyword)
        print(f"🔍 查询: '{search_keyword}' ({start_date} ~ {end_date})")

        try:
            # 构建过滤器
            filter_args = {
                "keyword": search_keyword,
                "start_date": start_date,
                "end_date": end_date,
            }

            if country:
                filter_args["country"] = country
            if domain:
                filter_args["domain"] = domain

            filters = Filters(**filter_args)

            # 执行查询
            articles = self.client.article_search(filters)

            if articles is not None and not articles.empty:
                print(f"✅ 找到 {len(articles)} 条新闻")
                return articles
            else:
                print("⚠️ 未找到相关新闻")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ 查询失败: {e}")
            return pd.DataFrame()

    def _batch_search(
        self,
        keyword: str,
        start_dt: datetime,
        end_dt: datetime,
        country: Optional[list] = None,
        domain: Optional[list] = None,
        language: str = "Chinese",
    ) -> pd.DataFrame:
        """分批查询（处理超过 90 天的请求）"""
        all_results = []
        current_end = end_dt

        while current_end > start_dt:
            current_start = max(start_dt, current_end - timedelta(days=self.MAX_DAYS))

            df = self._single_search(
                keyword,
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d"),
                country,
                domain,
                language,
            )

            if not df.empty:
                all_results.append(df)

            current_end = current_start - timedelta(days=1)

        if all_results:
            combined = pd.concat(all_results, ignore_index=True)
            # 去重
            if "url" in combined.columns:
                combined = combined.drop_duplicates(subset=["url"])
            print(f"📊 合计找到 {len(combined)} 条新闻")
            return combined

        return pd.DataFrame()

    def search_stock_news(self, stock_name: str, days: int = 30) -> pd.DataFrame:
        """
        查询股票相关新闻（针对中国股票优化）

        Args:
            stock_name: 股票名称，如 "茅台"、"比亚迪"
            days: 查询天数

        Returns:
            新闻 DataFrame
        """
        # 中国财经新闻域名
        cn_finance_domains = [
            "sina.com.cn",
            "eastmoney.com",
            "10jqka.com.cn",
            "163.com",
            "qq.com",
            "hexun.com",
            "caixin.com",
            "yicai.com",
        ]

        return self.search(
            keyword=stock_name, days=days, country=["China"], domain=cn_finance_domains
        )


def format_news_output(df: pd.DataFrame, limit: int = 20) -> str:
    """格式化新闻输出"""
    if df.empty:
        return "未找到相关新闻"

    output = []
    output.append(f"\n{'=' * 80}")
    output.append(f"共找到 {len(df)} 条新闻 (显示前 {min(limit, len(df))} 条)")
    output.append(f"{'=' * 80}\n")

    # 获取列名
    title_col = next((c for c in ["title", "Title"] if c in df.columns), None)
    url_col = next((c for c in ["url", "URL"] if c in df.columns), None)
    date_col = next(
        (c for c in ["seendate", "DateTime", "date"] if c in df.columns), None
    )
    domain_col = next((c for c in ["domain", "Domain"] if c in df.columns), None)

    for i, (_, row) in enumerate(df.head(limit).iterrows(), 1):
        title = row[title_col] if title_col else "N/A"
        url = row[url_col] if url_col else ""
        date = row[date_col] if date_col else ""
        domain = row[domain_col] if domain_col else ""

        # 截断过长的标题
        if len(str(title)) > 80:
            title = title[:77] + "..."

        output.append(f"{i:2d}. [{date[:10] if date else 'N/A'}] {title}")
        if domain:
            output.append(f"    来源: {domain}")
        if url:
            output.append(f"    链接: {url[:80]}...")
        output.append("")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="GDELT 新闻查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python gdelt_query.py "茅台"
  python gdelt_query.py "茅台" --days 90
  python gdelt_query.py "贵州茅台" --start 2024-10-01 --end 2024-12-31
  python gdelt_query.py "比亚迪" --stock  # 使用中国财经网站过滤
  python gdelt_query.py "茅台" --output news.csv  # 保存到文件

注意: GDELT 2.0 Doc API 官方只支持最近 3 个月的新闻
      如需查询一年或更久的历史，请使用 Google BigQuery
        """,
    )

    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument(
        "--days", type=int, default=30, help="查询天数 (默认: 30, 最大: 90)"
    )
    parser.add_argument("--start", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument(
        "--stock", action="store_true", help="股票新闻模式（使用中国财经网站过滤）"
    )
    parser.add_argument("--output", "-o", help="输出到 CSV 文件")
    parser.add_argument("--limit", type=int, default=20, help="显示条数 (默认: 20)")

    args = parser.parse_args()

    if not GDELT_AVAILABLE:
        print("❌ 请先安装 gdeltdoc: pip install gdeltdoc")
        return

    client = GDELTNewsClient()

    # 执行查询
    if args.stock:
        df = client.search_stock_news(args.keyword, days=args.days)
    else:
        df = client.search(
            keyword=args.keyword,
            start_date=args.start,
            end_date=args.end,
            days=args.days,
        )

    # 输出结果
    print(format_news_output(df, limit=args.limit))

    # 保存到文件
    if args.output and not df.empty:
        df.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"✅ 已保存到 {args.output}")

    # 显示统计信息
    if not df.empty and "domain" in df.columns:
        print("\n📊 来源分布:")
        domain_counts = df["domain"].value_counts().head(10)
        for domain, count in domain_counts.items():
            print(f"   {domain}: {count} 条")


if __name__ == "__main__":
    main()
