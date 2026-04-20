#!/usr/bin/env python3
"""Basic tests for PPTx RAG"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config():
    """Test configuration loading"""
    from src.config import config

    print("Testing config...")
    assert config.api_base_url is not None
    assert config.llm_model is not None
    assert config.embedding_model is not None
    assert config.data_dir is not None
    print("  ✓ Config loaded successfully")


def test_models():
    """Test Pydantic models"""
    from src.models import SlideContent, PageChunk, ParentChunk

    print("Testing models...")
    slide = SlideContent(page_number=1, title="Test", text="Content")
    assert slide.page_number == 1
    print("  ✓ SlideContent model works")

    chunk = PageChunk(
        id="test_1",
        file_name="test.pptx",
        page_number=1,
        content="Test content",
    )
    assert chunk.id == "test_1"
    print("  ✓ PageChunk model works")

    parent = ParentChunk(
        id="parent_1_3",
        file_name="test.pptx",
        start_page=1,
        end_page=3,
        content="Merged content",
        child_chunk_ids=["test_1", "test_2", "test_3"],
    )
    assert len(parent.child_chunk_ids) == 3
    print("  ✓ ParentChunk model works")


def test_merger():
    """Test merger functionality"""
    from src.processor import check_title_similarity, merge_continuous_pages
    from src.models import SlideContent

    print("Testing merger...")

    # Test title similarity
    assert check_title_similarity("产品介绍", "产品介绍") is True  # Exact match
    assert check_title_similarity("产品介绍", "产品介绍续") is True  # Contains
    assert check_title_similarity("产品介绍", "财务报告") is False  # Different
    print("  ✓ Title similarity check works")

    # Test page merging
    slides = [
        SlideContent(page_number=1, title="产品介绍", text="内容1"),
        SlideContent(page_number=2, title="产品介绍", text="内容2"),
        SlideContent(page_number=3, title="财务报告", text="内容3"),
    ]

    groups = merge_continuous_pages(slides)
    assert len(groups) == 2
    assert groups[0].start_page == 1
    assert groups[0].end_page == 2
    print("  ✓ Page merging works")


def test_storage():
    """Test storage functionality"""
    from src.storage import DocStore
    from src.models import ParentChunk
    import tempfile
    import os

    print("Testing storage...")

    with tempfile.TemporaryDirectory() as tmpdir:
        store = DocStore(store_dir=tmpdir)

        parent = ParentChunk(
            id="test_parent",
            file_name="test.pptx",
            start_page=1,
            end_page=3,
            content="Test content",
            child_chunk_ids=["child1", "child2"],
        )

        # Test save
        assert store.save(parent) is True
        print("  ✓ DocStore save works")

        # Test get
        retrieved = store.get_by_id("test_parent")
        assert retrieved is not None
        assert retrieved.id == "test_parent"
        print("  ✓ DocStore get works")

        # Test delete
        assert store.delete("test_parent") is True
        assert store.get_by_id("test_parent") is None
        print("  ✓ DocStore delete works")


def test_rag_chain():
    """Test RAG chain initialization"""
    from src.rag.chain import RAGChain

    print("Testing RAGChain...")

    chain = RAGChain()
    assert chain is not None
    assert chain.llm is not None
    assert chain.doc_store is not None
    assert chain.vector_store is not None
    print("  ✓ RAGChain initializes correctly")


def main():
    """Run all tests"""
    print("=" * 50)
    print("Running PPTx RAG tests")
    print("=" * 50)
    print()

    tests = [
        test_config,
        test_models,
        test_merger,
        test_storage,
        test_rag_chain,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ FAILED: {e}")
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
