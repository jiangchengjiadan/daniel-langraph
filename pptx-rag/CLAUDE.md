# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Document RAG - An intelligent Q&A system for documents that supports multiple formats (PPT, PDF, Text, Images), extracts text and images, performs semantic search, and provides answers with image references using a parent-child chunking architecture.

**Tech Stack**: LangChain, OpenAI-compatible API (ChatOpenAI + OpenAIEmbeddings), FAISS vector store, BM25+Vector hybrid retrieval, Streamlit frontend, PyMuPDF (PDF parsing).

**Supported Formats**:
- PowerPoint: .pptx, .ppt (extracts text and images)
- PDF: .pdf (extracts text)
- Text: .txt, .md, .markdown, .log, .text (chunks by lines)
- Images: .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff (Vision API analysis)

## Prerequisites

- OpenAI-compatible API endpoint and API key
- Python dependencies in `requirements.txt`
- No local model installation required

## Common Commands

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start application
streamlit run app/streamlit_app.py

# Debug/test pipeline (outputs to data/debug/)
python debug_pipeline.py [pptx_file] -o data/debug -q "your question"
python debug_pipeline.py --qa  # Run full Q&A test
```

### Testing

```bash
# Run basic tests
python -m pytest tests/test_basic.py

# Run single test
python -m pytest tests/test_basic.py::test_name -v
```

### Environment Setup

- Copy `.env.example` to `.env` and configure settings
- Required settings:
  - `API_BASE_URL`: Your OpenAI-compatible API endpoint (e.g., `https://api.openai.com/v1`)
  - `API_KEY`: Your API key
  - `LLM_MODEL`: Model name (e.g., `gpt-4`, `qwen-max`)
  - `EMBEDDING_MODEL`: Embedding model (e.g., `text-embedding-3-large`)
- Configure retrieval weights: `BM25_WEIGHT` and `VECTOR_WEIGHT` (should sum to 1.0)
- Supports any OpenAI-compatible API: OpenAI, 阿里云通义千问, 智谱 AI, etc.

## Architecture

### Core RAG Pipeline (src/rag/chain.py)

`RAGChain` is the main orchestrator implementing a **singleton pattern**. Key processing steps:

1. **Text Extraction** (`src/parser/pptx_parser.py`) - Extracts slides with text, titles, and notes
2. **Image Extraction** (`src/parser/image_handler.py`) - Saves images to `data/images/{hash}/` and serves via HTTP
3. **Title Generation** (`src/processor/title_generator.py`) - LLM generates titles for slides without titles
4. **Page Filtering** (`src/processor/`) - Removes cover page and invalid slides (TOC, "Thank You" pages, etc.)
5. **Page Merging** (`src/processor/merger.py`) - Groups consecutive pages with similar titles or manual markers
6. **Child Chunking** (`src/processor/chunking.py`) - Creates individual page chunks with image placeholders
7. **Parent Building** (`src/processor/parent_builder.py`) - Builds merged parent chunks from merge groups
8. **Storage** - Child chunks → FAISS (`src/storage/vector_store.py`), Parent chunks → JSON DocStore (`src/storage/doc_store.py`)

### Parent-Child Chunking Architecture

This is the **critical architectural pattern** that enables accurate context retrieval:

- **Child Chunks**: Individual page content, vectorized and stored in FAISS for fast semantic search
- **Parent Chunks**: Merged multi-page content stored in DocStore, used as LLM context
- **Mapping**: Each child chunk has `parent_id` in metadata linking to its parent
- **Retrieval Flow**:
  1. Hybrid search returns relevant child chunks
  2. System looks up parent chunks via `child_to_parent_map`
  3. Parent content (with full multi-page context) is fed to LLM

This avoids feeding fragmented single-page context to the LLM while maintaining precise retrieval.

### Page Merging Strategy

Pages are merged into parent chunks using two methods:

1. **Automatic Title Similarity** (`src/processor/merger.py:check_title_similarity`) - Pages with similar/identical titles are grouped
2. **Manual Markers** - Add to slide notes:
   - `<START_BLOCK>` - Force start of new merge group
   - `<END_BLOCK>` - Force end of current merge group

### Hybrid Retrieval (src/retriever/hybrid_retriever.py)

Combines two retrieval methods with configurable weights:

- **BM25**: Keyword-based matching (good for exact terms)
- **Vector Search**: Semantic similarity via embeddings (good for conceptual matching)
- **Deduplication**: Results are deduplicated by page number
- **Dynamic Weights**: Adjustable at runtime via Streamlit UI (`set_weights()`)

### Image Handling

Images are preserved in answers using this workflow:

1. Extract images from PPTX, save to `data/images/{file_hash}/{page}_{idx}.png`
2. Start HTTP server (`src/server/image_server.py`) on port 8080
3. Insert Markdown placeholders: `![description](http://localhost:8080/...)`
4. LLM must preserve these placeholders in answers (emphasized in prompt)
5. Streamlit renders markdown with images

**Important**: The QA prompt (`src/rag/chain.py:_build_qa_prompt`) heavily emphasizes image preservation to prevent LLM from dropping image links.

### Data Storage

- `data/uploads/` - Uploaded PPTX files
- `data/images/{hash}/` - Extracted images (hash = first 8 chars of MD5(filename))
- `data/chunks/` - Parent chunks as individual JSON files
- `data/indexes/pptx_rag/` - FAISS vector index
- `data/logs/` - Application logs

### Configuration (src/config.py)

`Config` class is a singleton that loads from `.env`. Key settings:

- **API**: `API_BASE_URL`, `API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`
- **LLM**: `LLM_TEMPERATURE`, `LLM_NUM_CTX`, `LLM_NUM_PREDICT` (note: `max_tokens` for API)
- **Retrieval**: `RETRIEVAL_K` (results count), `RETRIEVAL_K_MULTIPLIER` (internal fetch multiplier)
- **Weights**: `BM25_WEIGHT`, `VECTOR_WEIGHT`

### Data Models (src/models.py)

Pydantic models define the data flow:

- `SlideContent` - Raw extracted slide data
- `PageChunk` - Child chunk for vector storage (has `parent_id` in metadata)
- `ParentChunk` - Merged parent chunk with `child_chunk_ids`
- `MergeGroup` - Temporary grouping during merge phase
- `AnswerResult` - Final answer with sources and referenced pages

## Key Implementation Patterns

### Singleton Pattern

Both `RAGChain` and `Config` use singleton pattern to ensure single instances across the application (critical for Streamlit which may re-execute code on interactions).

### LLM Warmup

`RAGChain.warmup()` is called at app startup (in `app/streamlit_app.py`) to pre-load the Ollama model and establish connection, avoiding first-query latency.

### Duplicate Document Handling

When re-uploading an existing file (matched by filename):

1. Delete from DocStore (all parent chunks)
2. Delete from VectorStore (all child chunks)
3. Delete images directory
4. Delete uploaded file
5. Process new upload fresh

This is handled in `RAGChain.load_document()` and `RAGChain.clear()`.

### Context Building for LLM (src/retriever/parent_retriever.py)

The `get_parent_context()` function:

1. Takes retrieved child chunks
2. Looks up parent chunks via `child_to_parent_map`
3. Deduplicates parent chunks
4. Formats context with clear markers: `参考来源 N (父块，页面 X-Y)` or `参考来源 N (页面 X)`
5. Returns combined text fed to LLM

This ensures the LLM sees full merged context, not fragmented pages.

### Streaming vs Non-Streaming Answers

- `RAGChain.ask()` - Returns complete answer (used in current UI)
- `RAGChain.ask_stream()` - Generator for streaming responses (available but not currently used)

Both share the same prompt builder (`_build_qa_prompt`) and retrieval logic.

## Development Guidelines

### When Modifying Retrieval

- Adjust weights in `.env` or via Streamlit UI
- Remember `RETRIEVAL_K_MULTIPLIER` fetches more results internally for filtering
- BM25 is reinitialized whenever vector store changes (`HybridRetriever._initialize_bm25()`)

### When Changing LLM Behavior

- Modify prompt in `src/rag/chain.py:_build_qa_prompt()`
- Current prompt heavily emphasizes image preservation - maintain this
- Temperature can be adjusted dynamically via `set_temperature()`

### When Adding New Document Types

- Implement parser following pattern in `src/parser/pptx_parser.py`
- Ensure text and images are extracted separately
- Add to `RAGChain.load_document()` pipeline

### Debugging

Use `debug_pipeline.py` to output detailed JSON files showing each processing stage:

```bash
python debug_pipeline.py your_file.pptx -o data/debug --qa
```

Outputs include: slides, titles, chunks, merge groups, parent chunks, search results, LLM context, and answers.

## Troubleshooting

### "API connection failed"

- Check `API_BASE_URL` in `.env` is correct
- Verify `API_KEY` is valid and has sufficient quota
- Test connection with a simple curl command to your API endpoint

### Images not showing

- Verify ImageServer is running (auto-started in Streamlit app)
- Check `IMAGE_SERVER_PORT` (default 8080) is not blocked
- Verify images exist in `data/images/{hash}/`

### Poor retrieval quality

- Adjust `BM25_WEIGHT` and `VECTOR_WEIGHT` (sum to 1.0)
- Increase `RETRIEVAL_K` for more results
- Check if pages need manual merge markers for better context

### Memory issues

- FAISS index size grows with documents
- Consider clearing old documents: UI "清空所有文档" button or `RAGChain.clear(file_name)`

### API rate limiting

- Check your API provider's rate limits
- Adjust `LLM_TEMPERATURE` and `LLM_NUM_PREDICT` to reduce token usage
- Consider implementing retry logic for production use
