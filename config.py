import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int

    MINIO_BASE_URL: str
    MINIO_URL: str
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str

    SPEECH_CONFIG_SUB_ID: str
    SPEECH_CONFIG_REGION: str
    SPEECH_CONFIG_VOICE: str
    SPEECH_CONFIG_ENDPOINT: str

    OTLP_ENDPOINT: str
    LLM_API_URL: str
    MEDIA_PATH: str
    EDITED_PATH: str


settings = Settings()
print(settings.OTLP_ENDPOINT)