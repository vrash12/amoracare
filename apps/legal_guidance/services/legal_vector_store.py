import json
import math
import os
from pathlib import Path
from typing import Any

from django.conf import settings
from openai import OpenAI


class LegalVectorStore:
    """
    Local JSON vector store for AmoraCare legal guidance.

    Stores chunks here:
    django-ai-service/knowledge_base/vector_store/legal_chunks.json
    """

    def __init__(self):
        self.base_dir = Path(settings.BASE_DIR)
        self.store_dir = self.base_dir / "knowledge_base" / "vector_store"
        self.store_path = self.store_dir / "legal_chunks.json"

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embed_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        self.store_dir.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        self.store_path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []

        try:
            return json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def save(self, records: list[dict[str, Any]]) -> None:
        self.store_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        existing_records = self.load()
        new_records = []

        for chunk in chunks:
            text = chunk.get("text", "").strip()

            if not text:
                continue

            embedding = self.embed(text)

            new_records.append({
                "source": chunk.get("source"),
                "source_path": chunk.get("source_path"),
                "chunk_index": chunk.get("chunk_index"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "text": text,
                "embedding": embedding,
            })

        all_records = existing_records + new_records
        self.save(all_records)

        return len(new_records)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        records = self.load()

        if not records:
            return []

        query_embedding = self.embed(query)

        scored_records = []

        for record in records:
            record_embedding = record.get("embedding")

            if not record_embedding:
                continue

            similarity = self.cosine_similarity(query_embedding, record_embedding)
            distance = 1 - similarity

            scored_records.append({
                "source": record.get("source"),
                "source_path": record.get("source_path"),
                "chunk_index": record.get("chunk_index"),
                "page_start": record.get("page_start"),
                "page_end": record.get("page_end"),
                "text": record.get("text"),
                "distance": distance,
                "similarity": similarity,
            })

        scored_records.sort(key=lambda item: item["distance"])

        return scored_records[:limit]

    def embed(self, text: str) -> list[float]:
        text = text.strip()

        if not text:
            raise ValueError("Cannot embed empty text.")

        response = self.client.embeddings.create(
            model=self.embed_model,
            input=text,
        )

        return response.data[0].embedding

    @staticmethod
    def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
        if not vector_a or not vector_b:
            return 0.0

        if len(vector_a) != len(vector_b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(x * x for x in vector_a))
        norm_b = math.sqrt(sum(y * y for y in vector_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)