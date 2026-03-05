# src/retriever/hybrid_retriever.py
"""Hybrid retriever combining BM25 and Vector search"""

from typing import List, Optional, Dict, Any
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from ..config import config
from ..storage.vector_store import VectorStore
from ..models import PageChunk
from ..logging import log


class HybridRetriever:
    """Hybrid retriever combining BM25 and Vector search"""

    def __init__(self, vector_store: VectorStore = None):
        """
        Initialize hybrid retriever

        Args:
            vector_store: Optional VectorStore instance
        """
        self.log = log.bind(module="hybrid_retriever")
        self.vector_store = vector_store or VectorStore()
        self.bm25_retriever: Optional[BM25Retriever] = None
        # Default values from config
        self.bm25_weight = config.bm25_weight
        self.vector_weight = config.vector_weight
        self.retrieval_k = config.retrieval_k  # 运行时可调整
        self._initialize_bm25()

    def set_weights(self, bm25_weight: float = None, vector_weight: float = None):
        """
        Set retrieval weights dynamically

        Args:
            bm25_weight: BM25 weight (0.0-1.0)
            vector_weight: Vector weight (0.0-1.0)
        """
        if bm25_weight is not None:
            self.bm25_weight = bm25_weight
        if vector_weight is not None:
            self.vector_weight = vector_weight
        self.log.info(f"Weights updated: BM25={self.bm25_weight}, Vector={self.vector_weight}")

    def _initialize_bm25(self):
        """Initialize BM25 retriever from vector store content"""
        if self.vector_store.vector_store is None:
            return

        try:
            # Get all documents from vector store
            docs = []
            for doc in self.vector_store.vector_store.docstore._dict.values():
                docs.append(
                    Document(
                        page_content=doc.page_content,
                        metadata=doc.metadata,
                    )
                )

            if docs:
                self.bm25_retriever = BM25Retriever.from_documents(docs)
                self.log.info(f"Initialized BM25 retriever with {len(docs)} documents")
            else:
                self.log.warning("No documents for BM25 retriever")

        except Exception as e:
            self.log.warning(f"Failed to initialize BM25 retriever: {e}")

    def get_relevant_documents(
        self,
        query: str,
        k: int = None,
        file_name: str = None,
    ) -> List[PageChunk]:
        """
        Get relevant documents using hybrid search

        Args:
            query: Search query
            k: Number of results (uses self.retrieval_k if None)
            file_name: Optional file name filter

        Returns:
            List of relevant PageChunk objects
        """
        import time
        t0 = time.time()

        # Use instance retrieval_k if not specified
        if k is None:
            k = self.retrieval_k

        results = {"bm25": [], "vector": []}

        # BM25 search
        t_bm25 = time.time()
        if self.bm25_retriever:
            try:
                bm25_results = self.bm25_retriever.invoke(query)
                for doc in bm25_results:
                    if file_name is None or doc.metadata.get("file_name") == file_name:
                        results["bm25"].append(doc)
            except Exception as e:
                self.log.warning(f"BM25 search failed: {e}")
        t_bm25_end = time.time()
        self.log.info(f"[RETRIEVER] BM25: {t_bm25_end - t_bm25:.2f}s, found {len(results['bm25'])}")

        # Vector search
        t_vec = time.time()
        vector_results = self.vector_store.search(query, k=k * config.retrieval_k_multiplier, file_name=file_name)
        t_vec_end = time.time()
        self.log.info(f"[RETRIEVER] Vector: {t_vec_end - t_vec:.2f}s, found {len(vector_results)}")
        results["vector"] = vector_results

        # Merge and deduplicate results
        t_merge = time.time()
        merged = self._merge_results(results["bm25"], results["vector"], k)
        t_merge_end = time.time()
        self.log.info(f"[RETRIEVER] Merge: {t_merge_end - t_merge:.2f}s")

        t_end = time.time()
        self.log.info(f"[RETRIEVER] Total: {t_end - t0:.2f}s, returned {len(merged)} results")
        return merged

    def _merge_results(
        self,
        bm25_docs: List[Document],
        vector_chunks: List[PageChunk],
        k: int,
    ) -> List[PageChunk]:
        """Merge BM25 and Vector results with weighted scoring"""
        # Convert vector chunks to a map for easy access
        vector_map = {chunk.id: chunk for chunk in vector_chunks}

        # Track seen page numbers
        seen_pages = set()
        merged = []

        # Combine results (weighted by type)
        weighted_results = []

        # Add BM25 results with weight
        for doc in bm25_docs:
            page_num = doc.metadata.get("page_number", 0)
            if page_num not in seen_pages:
                weighted_results.append({
                    "chunk": self._doc_to_chunk(doc),
                    "score": self.bm25_weight,
                    "source": "bm25",
                })

        # Add Vector results with weight
        for chunk in vector_chunks:
            if chunk.page_number not in seen_pages:
                weighted_results.append({
                    "chunk": chunk,
                    "score": self.vector_weight,
                    "source": "vector",
                })

        # Sort by score and return top k
        weighted_results.sort(key=lambda x: x["score"], reverse=True)

        for item in weighted_results:
            if len(merged) >= k:
                break
            if item["chunk"].page_number not in seen_pages:
                seen_pages.add(item["chunk"].page_number)
                merged.append(item["chunk"])

        return merged

    def _doc_to_chunk(self, doc: Document) -> PageChunk:
        """Convert a Document to PageChunk"""
        return PageChunk(
            id=doc.metadata.get("id", ""),
            file_name=doc.metadata.get("file_name", ""),
            page_number=doc.metadata.get("page_number", 0),
            content=doc.page_content,
            title=doc.metadata.get("title"),
            metadata=doc.metadata,
        )

    def add_documents(self, chunks: List[PageChunk]) -> bool:
        """
        Add documents to both retrievers

        Args:
            chunks: List of PageChunk objects

        Returns:
            True if successful
        """
        # Add to vector store
        success = self.vector_store.add_chunks(chunks)

        # Reinitialize BM25 with new documents
        self._initialize_bm25()

        return success

    def delete_by_file(self, file_name: str) -> int:
        """
        Delete documents for a file from both retrievers

        Args:
            file_name: Name of the file

        Returns:
            Number of deleted chunks
        """
        count = self.vector_store.delete_by_file(file_name)
        self._initialize_bm25()
        return count
