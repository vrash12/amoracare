import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pypdf import PdfReader

from apps.legal_guidance.services.legal_vector_store import LegalVectorStore


class Command(BaseCommand):
    help = "Ingest AmoraCare adoption law PDFs into the local legal vector store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear the existing vector store before ingesting.",
        )

        parser.add_argument(
            "--chunk-size",
            type=int,
            default=700,
            help="Maximum words per chunk.",
        )

        parser.add_argument(
            "--overlap",
            type=int,
            default=120,
            help="Number of overlapping words between chunks.",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)

        pdf_dir = base_dir / "knowledge_base" / "adoption_law"

        if not pdf_dir.exists():
            raise CommandError(f"Folder not found: {pdf_dir}")

        pdf_files = sorted(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            raise CommandError(f"No PDF files found in: {pdf_dir}")

        vector_store = LegalVectorStore()

        if options["reset"]:
            vector_store.reset()
            self.stdout.write(self.style.WARNING("Existing vector store cleared."))

        total_chunks = 0

        for pdf_file in pdf_files:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE(f"Reading: {pdf_file.name}"))

            pages = self.extract_pdf_pages(pdf_file)

            if not pages:
                self.stdout.write(
                    self.style.WARNING(
                        f"No readable text found in {pdf_file.name}. "
                        "This PDF may be scanned and may need OCR."
                    )
                )
                continue

            chunks = self.build_chunks(
                pdf_file=pdf_file,
                pages=pages,
                chunk_size=options["chunk_size"],
                overlap=options["overlap"],
            )

            if not chunks:
                self.stdout.write(
                    self.style.WARNING(f"No chunks created for {pdf_file.name}.")
                )
                continue

            inserted_count = vector_store.add_chunks(chunks)
            total_chunks += inserted_count

            self.stdout.write(
                self.style.SUCCESS(
                    f"Indexed {inserted_count} chunks from {pdf_file.name}."
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total indexed chunks: {total_chunks}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Vector store saved at: {vector_store.store_path}"
            )
        )

    def extract_pdf_pages(self, pdf_file: Path) -> list[dict]:
        pages = []

        reader = PdfReader(str(pdf_file))

        for page_index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            text = self.clean_text(text)

            if text:
                pages.append({
                    "page": page_index,
                    "text": text,
                })

        return pages

    def clean_text(self, text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        return text.strip()

    def build_chunks(
        self,
        pdf_file: Path,
        pages: list[dict],
        chunk_size: int,
        overlap: int,
    ) -> list[dict]:
        chunks = []

        combined_words = []

        for page_data in pages:
            page_number = page_data["page"]
            words = page_data["text"].split()

            for word in words:
                combined_words.append({
                    "word": word,
                    "page": page_number,
                })

        if not combined_words:
            return chunks

        start = 0
        chunk_index = 1

        while start < len(combined_words):
            end = min(start + chunk_size, len(combined_words))
            word_slice = combined_words[start:end]

            text = " ".join(item["word"] for item in word_slice).strip()

            if text:
                page_start = word_slice[0]["page"]
                page_end = word_slice[-1]["page"]

                chunks.append({
                    "source": pdf_file.stem,
                    "source_path": str(pdf_file),
                    "chunk_index": chunk_index,
                    "page_start": page_start,
                    "page_end": page_end,
                    "text": text,
                })

                chunk_index += 1

            if end >= len(combined_words):
                break

            start = end - overlap

            if start < 0:
                start = 0

        return chunks