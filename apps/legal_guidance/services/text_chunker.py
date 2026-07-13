class TextChunker:
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1200,
        overlap: int = 200,
    ) -> list[str]:
        cleaned_text = self._clean_text(text)

        if not cleaned_text:
            return []

        chunks = []
        start = 0

        while start < len(cleaned_text):
            end = start + chunk_size
            chunk = cleaned_text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start = end - overlap

            if start < 0:
                start = 0

        return chunks

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())