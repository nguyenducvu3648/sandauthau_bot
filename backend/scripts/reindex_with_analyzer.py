"""Reindex ES với mapping mới."""
import asyncio
import json
from pathlib import Path

async def reindex():
    """Tạo index mới với analyzer tiếng Việt."""
    from app.services.es_client import ESClient
    from app.config import settings

    es = ESClient.get_client()
    old_index = settings.ES_INDEX
    new_index = f"{old_index}_v2"

    # Load mapping
    mapping_path = Path(__file__).parent.parent / "config" / "es_mapping.json"
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    print(f"Tao index moi: {new_index}")

    # Xoa neu ton tai
    try:
        es.indices.delete(index=new_index)
    except:
        pass

    # Tao index voi mapping
    es.indices.create(index=new_index, body=mapping)

    # Reindex
    print(f"Reindex tu {old_index} -> {new_index}")
    es.reindex(
        body={
            "source": {"index": old_index},
            "dest": {"index": new_index}
        },
        wait_for_completion=True
    )

    # Swap alias
    print("Swap alias...")
    try:
        es.indices.delete_alias(index=old_index, name=settings.ES_INDEX)
    except:
        pass

    es.indices.put_alias(index=new_index, name=settings.ES_INDEX)

    print(f"Hoan tat. Index hien tai: {new_index}")
    print(f"  Cap nhat .env: ES_INDEX={new_index}")

if __name__ == "__main__":
    asyncio.run(reindex())
