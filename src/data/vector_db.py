"""Multi-category vector database manager using Chroma"""
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
import os

from config import EMBEDDING_PROVIDER, OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL


class MultiVectorDBManager:
    """Manages category-specific Chroma collections with configurable embeddings"""

    def __init__(self, persist_directory: Path, embedding_provider: str = None):
        self.persist_directory = persist_directory
        self.embedding_provider = embedding_provider or EMBEDDING_PROVIDER

        # Initialize client
        self.client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Set up embedding function
        self.embedding_function = self._create_embedding_function()

        self.collections = {}

    def _create_embedding_function(self):
        """Create embedding function based on provider"""
        if self.embedding_provider == "openai":
            if not OPENAI_API_KEY:
                print("WARNING: OpenAI embeddings requested but OPENAI_API_KEY not set. Falling back to local embeddings.")
                return embedding_functions.DefaultEmbeddingFunction()

            print(f"Using OpenAI embeddings: {OPENAI_EMBEDDING_MODEL}")
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=OPENAI_API_KEY,
                model_name=OPENAI_EMBEDDING_MODEL
            )
        else:
            # Use default local sentence-transformers
            print("Using local embeddings: sentence-transformers (free)")
            return embedding_functions.DefaultEmbeddingFunction()

    def get_or_create_collection(self, category: str) -> chromadb.Collection:
        """Lazy-load vector DB for a category"""
        if category not in self.collections:
            collection_name = f"{category}_vectordb"
            self.collections[category] = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"category": category},
                embedding_function=self.embedding_function
            )
        return self.collections[category]

    def index_documents(
        self,
        category: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None
    ):
        """Index documents into a category collection"""
        collection = self.get_or_create_collection(category)

        # Generate IDs if not provided
        if ids is None:
            ids = [self._generate_id(doc, i) for i, doc in enumerate(documents)]

        # Add documents in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            collection.add(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids
            )

    def search(
        self,
        category: str,
        query: str,
        n_results: int = 3,
        where: Optional[Dict] = None
    ) -> Dict:
        """Search specific vector DB"""
        collection = self.get_or_create_collection(category)

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where
        )

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "ids": results["ids"][0] if results["ids"] else []
        }

    def get_collection_count(self, category: str) -> int:
        """Get number of documents in a collection"""
        collection = self.get_or_create_collection(category)
        return collection.count()

    def collection_exists(self, category: str) -> bool:
        """Check if a collection exists and has documents"""
        try:
            collection = self.get_or_create_collection(category)
            return collection.count() > 0
        except Exception:
            return False

    def delete_collection(self, category: str):
        """Delete a collection"""
        collection_name = f"{category}_vectordb"
        try:
            self.client.delete_collection(collection_name)
            if category in self.collections:
                del self.collections[category]
        except Exception:
            pass

    def _generate_id(self, content: str, index: int) -> str:
        """Generate unique ID for a document"""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{content_hash}_{index}"

    def list_collections(self) -> List[str]:
        """List all available collections"""
        collections = self.client.list_collections()
        return [col.name.replace("_vectordb", "") for col in collections]
