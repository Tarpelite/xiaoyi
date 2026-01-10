import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend directory
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
load_dotenv(env_path)

class Settings:
    """Application settings"""

    # API Keys
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # External Services
    RAG_SERVICE_URL: str = os.getenv("RAG_SERVICE_URL", "")
    
    # CORS settings
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]
    
    @property
    def api_key(self) -> str:
        """Get API key, raise error if not set"""
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
