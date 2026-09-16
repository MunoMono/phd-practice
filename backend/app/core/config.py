from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Testamentary Traces Research"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "https://innovationdesign.io"]
    
    # Auth0
    AUTH0_DOMAIN: str = "dev-i4m880asz7y6j5sk.us.auth0.com"
    AUTH0_AUDIENCE: str = ""  # API identifier from Auth0 dashboard
    
    # Local Database (research data & vectors)
    # These will be read from environment variables first, then .env file, then use defaults
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "testamentary-traces")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # DDR Archive GraphQL API
    DDR_GRAPHQL_ENDPOINT: str = "https://api.ddrarchive.org/graphql"
    DDR_API_TOKEN: str = ""  # Optional authentication token
    
    # DDR Archive Database (read-only queries) - DEPRECATED, use GraphQL instead
    DDR_POSTGRES_USER: str = ""
    DDR_POSTGRES_PASSWORD: str = ""
    DDR_POSTGRES_HOST: str = ""
    DDR_POSTGRES_PORT: int = 5432
    DDR_POSTGRES_DB: str = "ddr_archive"
    
    @property
    def DDR_DATABASE_URL(self) -> str:
        if not self.DDR_POSTGRES_HOST:
            return ""
        return f"postgresql://{self.DDR_POSTGRES_USER}:{self.DDR_POSTGRES_PASSWORD}@{self.DDR_POSTGRES_HOST}:{self.DDR_POSTGRES_PORT}/{self.DDR_POSTGRES_DB}"
    
    # Active Turin local inference runtime
    TURIN_MODEL: str = os.getenv("TURIN_MODEL", "qwen3:8b-q4_K_M")
    TURIN_RUNTIME_VERSION: str = "turin-runtime-v2"
    TURIN_QWEN_NUM_CTX: int = int(os.getenv("TURIN_QWEN_NUM_CTX", "16384"))
    TURIN_QWEN_SOURCE_ANALYSIS_MAX_TOKENS: int = int(os.getenv("TURIN_QWEN_SOURCE_ANALYSIS_MAX_TOKENS", "1000"))
    TURIN_QWEN_CROSS_SOURCE_MAX_TOKENS: int = int(os.getenv("TURIN_QWEN_CROSS_SOURCE_MAX_TOKENS", "1000"))
    TURIN_QWEN_FINAL_SYNTHESIS_MAX_TOKENS: int = int(os.getenv("TURIN_QWEN_FINAL_SYNTHESIS_MAX_TOKENS", "768"))
    TURIN_QWEN_TEMPERATURE: float = float(os.getenv("TURIN_QWEN_TEMPERATURE", "0.2"))
    TURIN_ARCHIVE_FIRST_CORPUS_VERSION: str = os.getenv(
        "TURIN_ARCHIVE_FIRST_CORPUS_VERSION", "corpus_f40d78dbce52"
    )
    
    # Vector DB
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_DIMENSION: int = 384
    
    # S3 Storage
    S3_BUCKET: str = "testamentary-traces-research"
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    class Config:
        # Read from .env file if it exists, but environment variables take precedence
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Environment variables always override .env file values
        extra = "ignore"


settings = Settings()
