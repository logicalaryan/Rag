import re
from typing import List, Dict, Any


class DocumentParser:
    """Extracts raw text and pages from PDF, Markdown, and TXT files."""

    @staticmethod
    def parse_file(filepath: str) -> List[Dict[str, Any]]:
        if filepath.endswith(".pdf"):
            return DocumentParser._parse_pdf(filepath)
        elif filepath.endswith((".txt", ".md")):
            return DocumentParser._parse_text(filepath)
        else:
            raise ValueError(f"Unsupported file format: {filepath}")

    @staticmethod
    def _parse_pdf(filepath: str) -> List[Dict[str, Any]]:
        import pypdf
        pages = []
        reader = pypdf.PdfReader(filepath)
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": idx + 1, "text": text.strip()})
        return pages

    @staticmethod
    def _parse_text(filepath: str) -> List[Dict[str, Any]]:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return [{"page": 1, "text": content.strip()}]


class StructureAwareChunker:
    """Splits documents into overlapping chunks preserving sentence and paragraph boundaries."""

    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, filename: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks = []
        chunk_idx = 0

        for page_data in pages:
            page_num = page_data["page"]
            text = page_data["text"]

            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            current_chunk = ""

            for p in paragraphs:
                if len(current_chunk) + len(p) + 2 <= self.chunk_size:
                    current_chunk += ("\n\n" + p if current_chunk else p)
                else:
                    if current_chunk:
                        chunk_idx += 1
                        chunks.append({
                            "chunk_id": f"{filename}_p{page_num}_c{chunk_idx}",
                            "content": current_chunk,
                            "source": filename,
                            "page": page_num,
                        })
                        # Keep trailing overlap
                        current_chunk = current_chunk[-self.overlap :] + "\n\n" + p
                    else:
                        # Single huge paragraph: chunk by character slice
                        for i in range(0, len(p), self.chunk_size - self.overlap):
                            slice_text = p[i : i + self.chunk_size]
                            chunk_idx += 1
                            chunks.append({
                                "chunk_id": f"{filename}_p{page_num}_c{chunk_idx}",
                                "content": slice_text,
                                "source": filename,
                                "page": page_num,
                            })
                        current_chunk = ""

            if current_chunk.strip():
                chunk_idx += 1
                chunks.append({
                    "chunk_id": f"{filename}_p{page_num}_c{chunk_idx}",
                    "content": current_chunk.strip(),
                    "source": filename,
                    "page": page_num,
                })

        return chunks
