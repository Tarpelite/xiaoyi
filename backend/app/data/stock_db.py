import os
import json
from enum import Enum
from pymongo import MongoClient
from typing import Optional, List
from pydantic import BaseModel

from app.core.config import settings


def get_mongo_client():
    from urllib.parse import quote_plus

    # URL编码用户名和密码（处理特殊字符）
    username = quote_plus(settings.MONGODB_USERNAME)
    password = quote_plus(settings.MONGODB_PASSWORD)
    host = settings.MONGODB_HOST
    port = settings.MONGODB_PORT
    auth_db = settings.MONGODB_DATABASE

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
