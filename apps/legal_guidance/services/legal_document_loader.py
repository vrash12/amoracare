from pathlib import Path

from docx import Document
from pypdf import PdfReader


class LegalDocumentLoader:
    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".pdf",
        ".docx",
    }

    def load_documents(self, folder_path: str) -> list[dict]:
        folder = Path(folder_path)

        if not folder.exists():
            return []

        documents = []

        for file_path in folder.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            text = self._extract_text(file_path)

            if not text.strip():
                continue

            documents.append(
                {
                    "source": file_path.name,
                    "path": str(file_path),
                    "text": text,
                }
            )

        return documents

    def _extract_text(self, file_path: Path) -> str:
        extension = file_path.suffix.lower()

        if extension == ".txt":
            return file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        if extension == ".pdf":
            return self._extract_pdf_text(file_path)

        if extension == ".docx":
            return self._extract_docx_text(file_path)

        return ""

    def _extract_pdf_text(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                pages.append(
                    f"[Page {page_number}]\n{text}"
                )

        return "\n\n".join(pages)

    def _extract_docx_text(self, file_path: Path) -> str:
        document = Document(str(file_path))

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n\n".join(paragraphs)