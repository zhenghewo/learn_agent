"""
Step 01 - 配置管理概念

新增概念：
- Settings：集中管理配置
- get_settings()：从环境变量读取配置
- 本 Step 只讲配置，不连接数据库、不调用 LLM

运行：
    python3 learn_agent/step01_settings_concept.py

对应 pv0：
- text2sql/config.py
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = "sqlite:///:memory:"
    llm_provider: str = "mock"
    llm_model: str = "mock-chat"
    max_sql_retries: int = 3


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        llm_model=os.getenv("LLM_MODEL", "mock-chat"),
        max_sql_retries=int(os.getenv("MAX_SQL_RETRIES", "3")),
    )


def main() -> None:
    # settings = Settings('a','b')
    settings = get_settings()
    print(settings)


if __name__ == "__main__":
    main()
