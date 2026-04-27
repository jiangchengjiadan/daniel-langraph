# src/storage/vector_store.py
"""FAISS vector store for page chunks"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import config
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from ..models import PageChunk
from ..logging import log


class VectorStore:
    """FAISS-based vector store for page chunks"""

    def __init__(self, index_name: str = "pptx_rag"):
        """
        Initialize vector store

        Args:
            index_name: Name of the index
        """
        self.log = log.bind(module="vector_store")
        self.index_name = index_name
        self.index_dir = config.indexes_dir / index_name
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.embeddings = OpenAIEmbeddings(
            model=config.embedding_model,
            openai_api_base=config.api_base_url,
            openai_api_key=config.api_key,
        )

        self.vector_store: Optional[FAISS] = None
        self._load_index()

    def _load_index(self):
        """Load existing index if available"""
        if self.index_dir.exists() and any(self.index_dir.iterdir()):
            try:
                self.vector_store = FAISS.load_local(
                    str(self.index_dir),
                    self.embeddings,
                    index_name=self.index_name,
                    allow_dangerous_deserialization=True,
                )
                self.log.info(f"Loaded existing index from {self.index_dir}")
            except Exception as e:
                self.log.warning(f"Failed to load index: {e}")
                self.vector_store = None

    def add_chunks(self, chunks: List[PageChunk]) -> bool:
        """
        Add page chunks to the vector store

        Args:
            chunks: List of PageChunk objects

        Returns:
            True if successful
        """
        if not chunks:
            return True

        try:
            documents = []
            for chunk in chunks:
                doc = Document(
                    page_content=chunk.content,
                    metadata={
                        "id": chunk.id,
                        "file_name": chunk.file_name,
                        "page_number": chunk.page_number,
                        "title": chunk.title or "",
                        **chunk.metadata,
                    },
                )
                documents.append(doc)

            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(
                    documents,
                    self.embeddings,
                )
            else:
                self.vector_store.add_documents(documents)

            self._save_index()
            self.log.info(f"Added {len(chunks)} chunks to vector store")
            return True

        except Exception as e:
            self.log.error(f"Failed to add chunks: {e}")
            return False

    def search(
        self,
        query: str,
        k: int = 5,
        file_name: str = None,
    ) -> List[PageChunk]:
        """
        Search for relevant chunks

        Args:
            query: Search query
            k: Number of results
            file_name: Optional file name filter

        Returns:
            List of relevant PageChunk objects
        """
        import time
        t0 = time.time()

        if self.vector_store is None:
            self.log.warning("Vector store not initialized")
            return []

        try:
            # Search with optional filter
            search_kwargs = {"k": k * config.retrieval_k_multiplier}

            if file_name:
                search_kwargs["filter"] = {"file_name": file_name}

            t1 = time.time()
            results = self.vector_store.similarity_search(
                query,
                **search_kwargs,
            )
            t2 = time.time()
            self.log.info(f"[VECTOR_SEARCH] FAISS search: {t2-t1:.2f}s, found {len(results)}")

            # Filter and limit results
            filtered_results = []
            seen_pages = set()

            for doc in results:
                page_num = doc.metadata.get("page_number", 0)
                if page_num not in seen_pages:
                    seen_pages.add(page_num)
                    filtered_results.append(doc)

                if len(filtered_results) >= k:
                    break

            # Convert to PageChunk objects
            chunks = []
            for doc in filtered_results:
                chunk = PageChunk(
                    id=doc.metadata.get("id", ""),
                    file_name=doc.metadata.get("file_name", ""),
                    page_number=doc.metadata.get("page_number", 0),
                    content=doc.page_content,
                    title=doc.metadata.get("title"),
                    metadata=doc.metadata,
                )
                chunks.append(chunk)

            t3 = time.time()
            self.log.info(f"[VECTOR_SEARCH] Total: {t3-t0:.2f}s, returned {len(chunks)} chunks")
            return chunks

        except Exception as e:
            self.log.error(f"Search failed: {e}")
            return []

    def _save_index(self):
        """Save the index to disk"""
        if self.vector_store:
            try:
                self.vector_store.save_local(
                    str(self.index_dir),
                    index_name=self.index_name,
                )
                self.log.debug(f"Saved index to {self.index_dir}")
            except Exception as e:
                self.log.error(f"Failed to save index: {e}")

    def delete_by_file(self, file_name: str) -> int:
        """
        Delete all chunks for a file

        Args:
            file_name: Name of the file

        Returns:
            Number of deleted chunks
        """
        if self.vector_store is None:
            return 0

        try:
            # Get all IDs for this file
            ids_to_delete = []
            for doc in self.vector_store.docstore._dict.values():
                if doc.metadata.get("file_name") == file_name:
                    ids_to_delete.append(doc.metadata.get("id"))

            if ids_to_delete:
                self.vector_store.delete(ids_to_delete)
                self._save_index()
                self.log.info(f"Deleted {len(ids_to_delete)} chunks for {file_name}")

            return len(ids_to_delete)

        except Exception as e:
            self.log.error(f"Failed to delete chunks: {e}")
            return 0

    def clear(self) -> int:
        """
        Clear the entire vector store

        Returns:
            Number of deleted chunks
        """
        count = 0
        if self.vector_store is None:
            self.log.warning("Vector store is None, nothing to clear")
            return 0

        try:
            count = len(self.vector_store.docstore._dict)
            self.log.info(f"Found {count} chunks to clear from vector store")

            # Reinitialize with empty index
            self.vector_store = FAISS.from_texts(
                ["placeholder"],
                self.embeddings,
            )
            # Try to delete placeholder, ignore if it doesn't exist
            try:
                self.vector_store.delete(["placeholder"])
            except Exception:
                pass  # Ignore if placeholder doesn't exist
            self._save_index()
            self.log.info(f"Cleared {count} chunks from vector store and saved empty index")
        except Exception as e:
            self.log.error(f"Failed to clear vector store: {e}")

        return count
