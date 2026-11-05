"""
Inspect category/lĩnh vực field trong ES index.
Kiểm tra xem field category có tồn tại không, định dạng như thế nào.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from elasticsearch import Elasticsearch
import json
from collections import Counter

def inspect_category():
    es = Elasticsearch(
        ['https://localhost:9200'],
        basic_auth=('elastic', 'httd99550'),
        verify_certs=False
    )
    index_name = 'dauthaus_prod_526k_v2'

    # 1. Check mapping
    print("=== Category Mapping ===")
    mapping = es.indices.get_mapping(index=index_name)
    properties = mapping[index_name]['mappings']['properties']

    if 'category' in properties:
        print(f"✓ Field 'category' tồn tại")
        print(f"Type: {json.dumps(properties['category'], indent=2, ensure_ascii=False)}")
    else:
        print("✗ Field 'category' KHÔNG tồn tại")
        print(f"Available fields: {list(properties.keys())}")
        return

    # 2. Sample values
    print("\n=== Sample Category Values (1000 docs) ===")
    result = es.search(
        index=index_name,
        body={
            "_source": ["category"],
            "size": 1000,
            "query": {"exists": {"field": "category"}}
        }
    )

    categories = []
    for hit in result['hits']['hits']:
        cat = hit['_source'].get('category')
        if cat:
            if isinstance(cat, list):
                categories.extend(cat)
            else:
                categories.append(cat)

    if not categories:
        print("✗ Không tìm thấy giá trị category nào")
        return

    print(f"Tổng {len(categories)} giá trị category từ {len(result['hits']['hits'])} docs")

    # 3. Top categories
    print("\n=== Top 20 Categories ===")
    counter = Counter(categories)
    for cat, count in counter.most_common(20):
        print(f"{count:6d} | {cat}")

    # 4. Total unique
    print(f"\n=== Summary ===")
    print(f"Unique categories: {len(counter)}")
    print(f"Avg categories per doc: {len(categories) / len(result['hits']['hits']):.2f}")

    # 5. Check normalization
    print("\n=== Normalization Check ===")
    sample_cats = [cat for cat, _ in counter.most_common(5)]
    for cat in sample_cats:
        has_upper = any(c.isupper() for c in cat)
        has_special = any(c in cat for c in '.,;:!?')
        print(f"'{cat}': uppercase={has_upper}, special={has_special}")

if __name__ == '__main__':
    inspect_category()
