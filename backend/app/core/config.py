from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Epistemic Drift Research"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Local Database (research data & vectors)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "epistemic_drift"
    
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
    
    # Granite Model
    GRANITE_MODEL_PATH: str = "ibm-granite/granite-4.0-h-small-instruct"
    GRANITE_DEVICE: str = "cuda"  # or "cpu"
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    
    # Vector DB
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_DIMENSION: int = 384
    
    # S3 Storage
    S3_BUCKET: str = "epistemic-drift-research"
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
