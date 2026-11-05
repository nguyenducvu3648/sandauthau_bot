"""ETL pipeline configuration."""
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"

# MongoDB
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "dauthaus"
MONGO_COLLECTION = "biddings"

# Elasticsearch
ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"
ES_INDEX = "dauthaus_prod_526k"

# Embedding Model
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# Pipeline settings
BATCH_SIZE = 500
EMBED_BATCH = 16
ES_BULK = 250
