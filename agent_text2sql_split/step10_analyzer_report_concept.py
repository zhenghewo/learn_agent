"""
Step 10 - Analyzer Report 概念

新增概念：
- AnalyzerAgent
- Markdown 报告
- report_dir 落盘

本 Step 只讲分析报告，不讲 Text2SQL 流程。

运行：
    python3 learn_agent/step10_analyzer_report_concept.py

对应 pv0：
- text2sql/analyzer_agent.py
"""

from datetime import datetime
from pathlib import Path


class AnalyzerAgent:
    def __init__(self, report_dir: str = "learn_agent/outputs/reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self, question: str, sql: str, rows: list[tuple]) -> str:
        report = (
            "# 分析报告\n\n"
            f"- 问题：{question}\n"
            f"- SQL：`{sql}`\n"
            f"- 行数：{len(rows)}\n\n"
            "## 结论\n\n"
            f"查询返回 {len(rows)} 条数据：{rows}\n"
        )
        path = self.report_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path.write_text(report, encoding="utf-8")
        return f"{report}\n报告路径：{path}"


def main() -> None:
    analyzer = AnalyzerAgent()
    text = analyzer.analyze(
        "评分最高的电影是哪部？",
        "SELECT title, rating FROM movies ORDER BY rating DESC LIMIT 1",
        [("星际穿越", 9.4)],
    )
    print(text)


if __name__ == "__main__":
    main()
