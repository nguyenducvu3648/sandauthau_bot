"""Application configuration."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings."""

    # App
    APP_NAME: str = "DauThau Search API"
    VERSION: str = "4.0.0"

    # Elasticsearch
    ES_HOST: str = "https://localhost:9200"
    ES_URL: str = "https://localhost:9200"
    ES_USER: str = "elastic"
    ES_PASSWORD: str = "httd99550"
    ES_INDEX: str = "dauthaus_prod_526k_v2"
    ES_VERIFY_CERTS: bool = False

    # Elasticsearch - New system (added from P1)
    ELASTICSEARCH_URL: str = "https://localhost:9200"
    ELASTICSEARCH_USER: str = "elastic"
    ELASTICSEARCH_PASSWORD: str = "httd99550"
    ELASTICSEARCH_INDEX: str = "dauthaus_prod_526k_v2"
    ELASTICSEARCH_VERIFY_CERTS: bool = False

    # Embedding
    MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # Search
    DEFAULT_TOP_K: int = 10
    DEFAULT_MIN_SCORE: float = 0.5

    # Debug
    DEBUG_LLM: bool = False

    # RRF
    RRF_WEIGHT_BM25: float = 0.3
    RRF_WEIGHT_VECTOR: float = 0.7
    RRF_K_CONSTANT: int = 60

    # Ranking
    RANK_WEIGHT_SEARCH: float = 0.5
    RANK_WEIGHT_RECENCY: float = 0.2
    RANK_WEIGHT_VALUE: float = 0.15
    RANK_WEIGHT_EXACT: float = 0.15

    # LLM config - mặc định DeepSeek, custom được
    LLM_PROVIDER: str = "deepseek"  # deepseek|claude|openai

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_ENDPOINT: str = "https://api.deepseek.com/v1"
    DEEPSEEK_TEMPERATURE: float = 0.1
    DEEPSEEK_MAX_TOKENS: int = 1000

    # Claude
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_ENDPOINT: str = "https://api.anthropic.com/v1/messages"
    CLAUDE_TEMPERATURE: float = 0.1
    CLAUDE_MAX_TOKENS: int = 1000

    # Anthropic (for V4 search)
    ANTHROPIC_API_KEY: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_ENDPOINT: str = "https://api.openai.com/v1/chat/completions"
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_TOKENS: int = 1000

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")


settings = Settings()
