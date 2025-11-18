"""
Document Reader
===============

Extracts text from documents (PDF/DOCX/TXT) with full provenance tracking.

Features:
- Multi-format support (PDF, DOCX, TXT)
- Page-level extraction
- Paragraph segmentation
- Provenance metadata for every segment
- Handles various encodings and layouts
"""

import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import (
    DocumentSegment,
    Provenance,
    ExtractionMethod,
    DocumentFormat,
)

logger = logging.getLogger(__name__)


class DocumentReader:
    """
    Reads documents and extracts text segments with provenance.

    Supports PDF, DOCX, TXT formats.
    """

    def __init__(
        self,
        min_paragraph_words: int = 10,
        context_chars: int = 100,
    ):
        """
        Initialize document reader.

        Args:
            min_paragraph_words: Minimum words for a paragraph to be considered
            context_chars: Number of context characters before/after segment
        """
        self.min_paragraph_words = min_paragraph_words
        self.context_chars = context_chars
        self.logger = logger

    def read_document(self, file_path: Path) -> List[DocumentSegment]:
        """
        Read document and return list of segments with provenance.

        Args:
            file_path: Path to document

        Returns:
            List of DocumentSegment objects

        Raises:
            ValueError: If file format not supported
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine format
        suffix = file_path.suffix.lower()
        format_map = {
            ".pdf": DocumentFormat.PDF,
            ".docx": DocumentFormat.DOCX,
            ".txt": DocumentFormat.TXT,
            ".md": DocumentFormat.MARKDOWN,
        }

        doc_format = format_map.get(suffix)
        if not doc_format:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported: {list(format_map.keys())}"
            )

        self.logger.info(f"Reading {doc_format.value} document: {file_path.name}")

        # Route to appropriate reader
        if doc_format == DocumentFormat.PDF:
            return self._read_pdf(file_path)
        elif doc_format == DocumentFormat.DOCX:
            return self._read_docx(file_path)
        else:  # TXT, MARKDOWN
            return self._read_text(file_path)

    def _read_pdf(self, file_path: Path) -> List[DocumentSegment]:
        """
        Read PDF file.

        Uses pdfplumber if available, falls back to PyPDF2.
        """
        try:
            import pdfplumber
            return self._read_pdf_with_pdfplumber(file_path)
        except ImportError:
            self.logger.warning(
                "pdfplumber not available, falling back to PyPDF2. "
                "Install with: pip install pdfplumber"
            )
            try:
                import PyPDF2
                return self._read_pdf_with_pypdf2(file_path)
            except ImportError:
                raise ImportError(
                    "Neither pdfplumber nor PyPDF2 available. "
                    "Install with: pip install pdfplumber PyPDF2"
                )

    def _read_pdf_with_pdfplumber(self, file_path: Path) -> List[DocumentSegment]:
        """Read PDF using pdfplumber (preferred - better text extraction)."""
        import pdfplumber

        segments = []
        full_text = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if not page_text:
                    self.logger.warning(f"Page {page_num} has no extractable text")
                    continue

                # Split into paragraphs (double newline or significant spacing)
                paragraphs = self._segment_into_paragraphs(page_text)

                char_offset = sum(len(t) for t in full_text)

                for para_idx, para_text in enumerate(paragraphs):
                    # Skip short paragraphs
                    if len(para_text.split()) < self.min_paragraph_words:
                        continue

                    # Get context
                    para_start = char_offset
                    para_end = char_offset + len(para_text)
                    full_text_str = "".join(full_text)

                    context_before = full_text_str[
                        max(0, para_start - self.context_chars):para_start
                    ]
                    context_after = ""  # Will be populated as we read more

                    # Create provenance
                    provenance = Provenance(
                        source_file=str(file_path),
                        page_number=page_num,
                        paragraph_index=para_idx,
                        char_start=para_start,
                        char_end=para_end,
                        extraction_method=ExtractionMethod.PDFPLUMBER,
                        extraction_timestamp=datetime.utcnow(),
                        context_before=context_before,
                        context_after=context_after,
                    )

                    # Create segment
                    segment = DocumentSegment(
                        text=para_text,
                        provenance=provenance,
                        metadata={
                            "page_number": page_num,
                            "paragraph_index": para_idx,
                            "word_count": len(para_text.split()),
                        },
                    )

                    segments.append(segment)
                    char_offset = para_end

                full_text.append(page_text)

        self.logger.info(f"Extracted {len(segments)} segments from PDF")
        return segments

    def _read_pdf_with_pypdf2(self, file_path: Path) -> List[DocumentSegment]:
        """Read PDF using PyPDF2 (fallback)."""
        import PyPDF2

        segments = []
        full_text = []

        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()

                if not page_text:
                    continue

                paragraphs = self._segment_into_paragraphs(page_text)
                char_offset = sum(len(t) for t in full_text)

                for para_idx, para_text in enumerate(paragraphs):
                    if len(para_text.split()) < self.min_paragraph_words:
                        continue

                    provenance = Provenance(
                        source_file=str(file_path),
                        page_number=page_num + 1,  # 1-indexed
                        paragraph_index=para_idx,
                        char_start=char_offset,
                        char_end=char_offset + len(para_text),
                        extraction_method=ExtractionMethod.PYPDF2,
                    )

                    segment = DocumentSegment(
                        text=para_text,
                        provenance=provenance,
                        metadata={
                            "page_number": page_num + 1,
                            "paragraph_index": para_idx,
                        },
                    )

                    segments.append(segment)
                    char_offset += len(para_text)

                full_text.append(page_text)

        return segments

    def _read_docx(self, file_path: Path) -> List[DocumentSegment]:
        """Read DOCX file."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx not available. Install with: pip install python-docx"
            )

        segments = []
        doc = Document(file_path)

        char_offset = 0

        for para_idx, paragraph in enumerate(doc.paragraphs):
            para_text = paragraph.text.strip()

            # Skip empty or very short paragraphs
            if not para_text or len(para_text.split()) < self.min_paragraph_words:
                continue

            provenance = Provenance(
                source_file=str(file_path),
                page_number=None,  # DOCX doesn't have page concept
                paragraph_index=para_idx,
                char_start=char_offset,
                char_end=char_offset + len(para_text),
                extraction_method=ExtractionMethod.PYTHON_DOCX,
            )

            segment = DocumentSegment(
                text=para_text,
                provenance=provenance,
                metadata={
                    "paragraph_index": para_idx,
                    "style": paragraph.style.name if paragraph.style else None,
                },
            )

            segments.append(segment)
            char_offset += len(para_text)

        self.logger.info(f"Extracted {len(segments)} segments from DOCX")
        return segments

    def _read_text(self, file_path: Path) -> List[DocumentSegment]:
        """Read plain text file."""
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        text = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise ValueError(f"Could not decode file {file_path} with any encoding")

        # Segment into paragraphs
        paragraphs = self._segment_into_paragraphs(text)
        segments = []

        char_offset = 0

        for para_idx, para_text in enumerate(paragraphs):
            if len(para_text.split()) < self.min_paragraph_words:
                continue

            provenance = Provenance(
                source_file=str(file_path),
                page_number=None,
                paragraph_index=para_idx,
                char_start=char_offset,
                char_end=char_offset + len(para_text),
                extraction_method=ExtractionMethod.PLAIN_TEXT,
            )

            segment = DocumentSegment(
                text=para_text,
                provenance=provenance,
                metadata={"paragraph_index": para_idx},
            )

            segments.append(segment)
            char_offset += len(para_text)

        self.logger.info(f"Extracted {len(segments)} segments from text file")
        return segments

    def _segment_into_paragraphs(self, text: str) -> List[str]:
        """
        Segment text into paragraphs.

        Uses heuristics:
        - Double newline = paragraph break
        - Significant whitespace = paragraph break
        - Consistent indentation = preserve structure
        """
        # Split on double newlines first
        paragraphs = text.split('\n\n')

        # Further split on single newlines if paragraphs are too long
        result = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If paragraph is very long (>1000 chars), try to split on single newlines
            if len(para) > 1000:
                sub_paras = para.split('\n')
                for sub in sub_paras:
                    sub = sub.strip()
                    if sub and len(sub.split()) >= self.min_paragraph_words:
                        result.append(sub)
            else:
                # Clean up whitespace within paragraph
                para = ' '.join(para.split())
                if len(para.split()) >= self.min_paragraph_words:
                    result.append(para)

        return result
