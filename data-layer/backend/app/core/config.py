from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://paul:paul@db:5432/paul"
    STORAGE_PATH: str = "/storage/originals"
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "PAUL — Product Attribute Unified Layer"

    class Config:
        env_file = ".env"


settings = Settings()
