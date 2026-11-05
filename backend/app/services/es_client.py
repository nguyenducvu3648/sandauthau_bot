"""Elasticsearch client wrapper."""
from typing import Optional
from elasticsearch import Elasticsearch
from ..config import settings
import warnings

class ESClient:
    """Elasticsearch client singleton."""

    _instance: Optional[Elasticsearch] = None

    @classmethod
    def get_client(cls) -> Elasticsearch:
        """Get or create ES client."""
        if cls._instance is None:
            # Suppress SSL warnings nếu verify_certs=False
            if not settings.ES_VERIFY_CERTS:
                warnings.filterwarnings('ignore', message='Unverified HTTPS request')

            cls._instance = Elasticsearch(
                [settings.ES_URL],
                basic_auth=(settings.ES_USER, settings.ES_PASSWORD),
                verify_certs=settings.ES_VERIFY_CERTS,
                ssl_show_warn=False,
                request_timeout=60,  # Tăng lên 60s
                max_retries=3,
                retry_on_timeout=True
            )
        return cls._instance

    @classmethod
    def close(cls):
        """Close ES client."""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
