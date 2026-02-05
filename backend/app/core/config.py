from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Load .env settings are handled by pydantic, but we can set the default location
# 【修改】从项目根目录读取统一的 .env 文件
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Restore load_dotenv for libraries/scripts relying on os.environ
try:
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
except ImportError:
    pass


class Settings(BaseSettings):
    """
    Application settings using pydantic-settings

    Reads configuration from .env file or environment variables.
    No sensible defaults are hardcoded here to ensure security and flexibility.
    """

    # Model Config to load .env file
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",  # Identify extra fields in .env as ok
        case_sensitive=True,
    )

    # API Keys (Required)
    DEEPSEEK_API_KEY: str
    TAVILY_API_KEY: str

    # Server settings (Optional with standard defaults or set in .env)
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # External Services
    RAG_SERVICE_URL: str

    # Redis Settings
    REDIS_HOST: str
    REDIS_PORT: int = 6379  # Port usually safe to default but can be overridden
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_KEY_PREFIX: str = "stock:"

    # MongoDB Settings
    MONGODB_HOST: str
    MONGODB_PORT: int = 27017
    MONGODB_USERNAME: str
    MONGODB_PASSWORD: str
    MONGODB_DATABASE: str
    MONGODB_COLLECTION: str = "stock_news"

    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Authing Settings
    AUTHING_APP_ID: str
    AUTHING_APP_SECRET: str
    AUTHING_ISSUER: str

    @property
    def api_key(self) -> str:
        """Get API key, raise error if not set (Legacy compat)"""
        if not self.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not set in environment variables")
        return self.DEEPSEEK_API_KEY

    @property
    def tavily_api_key(self) -> str:
        """Get Tavily API key, raise error if not set"""
        if not self.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY not set in environment variables")
        return self.TAVILY_API_KEY


settings = Settings()
