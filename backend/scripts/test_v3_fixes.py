"""Quick test V3 fixes."""
import sys
sys.path.insert(0, '.')

from app.services.location_service import LocationService
from app.services.intent_analyzer_v3 import IntentAnalyzerV3


def main():
    # Test 1: Location multi-code
    codes = LocationService.get_province_codes('Hà Nội')
    assert len(codes) == 4, f'Expected 4 codes, got {len(codes)}'
    assert '101' in codes and '01' in codes, 'Missing codes'
    print('[OK] Location multi-code')

    # Test 2: Regex mã gói
    code = IntentAnalyzerV3._extract_code('gói thầu BP2200225863')
    assert code == 'BP2200225863', f'Regex failed: {code}'
    print('[OK] Regex mã gói thầu')

    # Test 3: Filter extract
    filters, residual = IntentAnalyzerV3._extract_filters_and_residual('gói thầu ở Hà Nội')
    assert 'location' in filters, 'Location not extracted'
    assert isinstance(filters['location'], list), 'Location should be list'
    assert len(filters['location']) == 4, f'Expected 4 codes, got {len(filters["location"])}'
    print('[OK] Filter location extract')

    # Test 4: Backward compat
    single = LocationService.get_province_code('TP. Hồ Chí Minh')
    assert single == '701', f'Expected 701, got {single}'
    print('[OK] Backward compat get_province_code')

    print('\n=== All 4 V3 mapping fixes validated ===')


if __name__ == '__main__':
    main()
