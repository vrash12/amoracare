from pathlib import Path
from django.conf import settings
from pypdf import PdfReader


class LegalContextService:
    """
    Reads local legal documents from django-ai-service/legal_documents.

    Supported:
    - .txt
    - .pdf

    This is the starter version.
    Later, we will replace this with real RAG chunk search.
    """

    def __init__(self):
        self.legal_documents_path = Path(settings.BASE_DIR) / "legal_documents"

    def get_context(self, max_characters: int = 12000) -> str:
        if not self.legal_documents_path.exists():
            return ""

        collected_context = []

        for file_path in self.legal_documents_path.rglob("*"):
            if file_path.is_dir():
                continue

            if file_path.suffix.lower() == ".txt":
                text = self._read_txt(file_path)
            elif file_path.suffix.lower() == ".pdf":
                text = self._read_pdf(file_path)
            else:
                continue

            if not text.strip():
                continue

            collected_context.append(
                f"\n\nSOURCE: {file_path.name}\n{text.strip()}"
            )

            current_size = sum(len(item) for item in collected_context)

            if current_size >= max_characters:
                break

        return "\n".join(collected_context)[:max_characters]

    def _read_txt(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _read_pdf(self, file_path: Path) -> str:
        try:
            reader = PdfReader(str(file_path))
            pages = []

            for page in reader.pages:
                page_text = page.extract_text() or ""
                pages.append(page_text)

            return "\n".join(pages)
        except Exception:
            return ""