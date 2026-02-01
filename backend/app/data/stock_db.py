import os
import json
from enum import Enum
from pymongo import MongoClient
from typing import Optional, List
from pydantic import BaseModel

MONGO_CONFIG = {
    "host": os.getenv("MONGODB_HOST", "10.139.197.230"),
    "port": int(os.getenv("MONGODB_PORT", "27017")),
    "username": os.getenv("MONGODB_USERNAME", "xiaoyi_user"),
    "password": os.getenv("MONGODB_PASSWORD", "ACTact123@buaa#"),
    "database": os.getenv("MONGODB_DATABASE", "xiaoyi_db"),
    "collection": os.getenv("MONGODB_COLLECTION", "stock_news"),
}


def get_mongo_client():
    from urllib.parse import quote_plus

    # URL编码用户名和密码（处理特殊字符）
    username = quote_plus(MONGO_CONFIG["username"])
    password = quote_plus(MONGO_CONFIG["password"])
    host = MONGO_CONFIG["host"]
    port = MONGO_CONFIG["port"]
    auth_db = MONGO_CONFIG["database"]

    # 使用URL格式连接字符串
    mongo_uri = (
        f"mongodb://{username}:{password}@{host}:{port}/{auth_db}?authSource={auth_db}"
    )

    return MongoClient(mongo_uri)


def ensure_mongodb_indexes(db, collection_name: str):
    """Ensure publish_time index exists for efficient date range queries"""
    try:
        collection = db[collection_name]
        existing_indexes = collection.index_information()

        if "publish_time_1" not in existing_indexes:
            collection.create_index([("publish_time", 1)])
            print(f"[MongoDB] Created index on publish_time for {collection_name}")
        else:
            print(
                f"[MongoDB] Index on publish_time already exists for {collection_name}"
            )
    except Exception as e:
        print(f"[MongoDB] Index creation warning: {e}")


class NewsItem(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    content_type: str
    publish_time: str
    source: Optional[str] = None
    url: Optional[str] = None
    read_count: int = 0
    comment_count: int = 0
    institution: Optional[str] = None
    grade: Optional[str] = None
    notice_type: Optional[str] = None
