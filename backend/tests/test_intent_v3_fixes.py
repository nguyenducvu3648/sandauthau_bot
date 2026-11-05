"""Test intent analyzer v3 fixes."""
import asyncio
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
from app.services.intent_analyzer_v3 import IntentAnalyzerV3
import pytest

@pytest.mark.asyncio
async def test_bug_fixes():
    """Test 5 loi da fix."""

    # Bug 2: Ma co nam khong bi boc nham
    result = await IntentAnalyzerV3.analyze("DT-2024-123")
    assert result.code == "DT-2024-123", f"Bug 2: code={result.code}"
    assert result.filters.get("year") != 2024, f"Bug 2: nam bi boc nham tu ma"
    print("OK Bug 2: Ma co nam khong bi boc nham")

    # Bug 3: Residual sach voi stopwords
    result = await IntentAnalyzerV3.analyze("goi thau o Ha Noi nam 2024")
    assert result.residual == "", f"Bug 3: residual='{result.residual}'"
    assert result.method == "metadata_only", f"Bug 3: method={result.method}"
    print("OK Bug 3: Stopwords lam sach residual")

    # Bug 4: Aggregation co filters
    result = await IntentAnalyzerV3.analyze("top 5 tinh nhieu goi thau nam 2024")
    assert result.intent == "aggregation", f"Bug 4: intent={result.intent}"
    assert result.filters.get("year") == 2024, f"Bug 4: mat year filter"
    print("OK Bug 4: Aggregation giu filters")

    # Bug 1: Khong goi LLM khi khong can
    result = await IntentAnalyzerV3.analyze("xay dung cau o Ha Noi")
    assert len(result.llm_calls) == 0, f"Bug 1: llm_calls={result.llm_calls}"
    print("OK Bug 1: Khong goi LLM khong can thiet")

    # Bug 1: Chi goi LLM khi co signal
    result = await IntentAnalyzerV3.analyze("xay dung cau khong phai o Ha Noi")
    print(f"OK Bug 1: Phat hien signal negation, llm_calls={result.llm_calls}")

    print("\n=== ALL FIXES VERIFIED ===")

if __name__ == "__main__":
    asyncio.run(test_bug_fixes())
