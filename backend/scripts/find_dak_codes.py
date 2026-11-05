"""Find Dak Lak/Dak Nong province codes from nested locations."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from elasticsearch import Elasticsearch
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

es = Elasticsearch(
    ['https://localhost:9200'],
    basic_auth=('elastic', 'httd99550'),
    verify_certs=False
)

result = es.search(
    index='dauthaus_prod_526k_v2',
    body={
        "_source": ["locations"],
        "size": 1000,
        "query": {
            "nested": {
                "path": "locations",
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"locations.provName": "Đắk Lắk"}},
                            {"match": {"locations.provName": "Đắk Nông"}},
                            {"match": {"locations.provName": "Dak Lak"}},
                            {"match": {"locations.provName": "Dak Nong"}}
                        ]
                    }
                }
            }
        }
    }
)

codes = Counter()
for hit in result['hits']['hits']:
    locs = hit['_source'].get('locations', [])
    for loc in locs:
        name = loc.get('provName', '')
        if 'Đắk' in name or 'Dak' in name or 'Đăk' in name:
            code = loc.get('provCode')
            codes[f'{code} ({name})'] += 1

print(f'Found {len(result["hits"]["hits"])} docs')
print('\nCodes:')
for key, count in codes.most_common():
    print(f'  {key}: {count}')
