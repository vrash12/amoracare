import time
import requests
from django.conf import settings


class OllamaEmbeddingService:
    def embed(
        self,
        texts: list[str],
        batch_size: int = 1,
        timeout: int = 180,
    ) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings = []
        total = len(texts)

        for start in range(0, total, batch_size):
            batch = texts[start:start + batch_size]

            response = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "input": batch,
                    "keep_alive": "15m",
                },
                timeout=timeout,
            )

            response.raise_for_status()

            data = response.json()
            embeddings = data.get("embeddings")

            if embeddings is None:
                raise ValueError(
                    f"Ollama did not return embeddings. Response: {data}"
                )

            all_embeddings.extend(embeddings)

            time.sleep(0.03)

        return all_embeddings