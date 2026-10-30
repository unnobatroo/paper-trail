"""pdf adapters, raw page text kept apart from the rendered structure"""
import hashlib
import io
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.models import DocumentPage

log = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    pages: list[DocumentPage]
    markdown: str
    provenance: dict = field(default_factory=dict)
    structured: dict = field(default_factory=dict)


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, content: bytes) -> ParsedDocument: ...


class PypdfDocumentParser(DocumentParser):
    def parse(self, content: bytes) -> ParsedDocument:
        from .pdf import read_pages
        pages = read_pages(content)
        return ParsedDocument(pages, "\n\n".join(
            f"<!-- page {p.page_number} -->\n{p.text}" for p in pages),
            {"parser": "pypdf", "ocr_pages": []})


class DoclingDocumentParser(DocumentParser):
    def __init__(self, device: str = "cpu", artifact_dir: Path | None = None):
        self.device = device
        self.artifact_dir = artifact_dir

    def parse(self, content: bytes) -> ParsedDocument:
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.io import DocumentStream
        options = ThreadedPdfPipelineOptions(
            do_ocr=True, do_table_structure=True,
            ocr_batch_size=1, layout_batch_size=1, table_batch_size=1,
            accelerator_options=AcceleratorOptions(device=self.device, num_threads=4))
        converter = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        stream = DocumentStream(name="source.pdf", stream=io.BytesIO(content))
        doc = converter.convert(stream).document
        raw = PypdfDocumentParser().parse(content)
        ocr_pages = []
        for page in raw.pages:
            if not page.text.strip():
                # ocr items carry exact page provenance, markdown is never a receipt
                page.text = "\n".join(
                    item.text for item, _ in doc.iterate_items()
                    if getattr(item, "text", "") and any(
                        p.page_no == page.page_number for p in getattr(item, "prov", [])))
                ocr_pages.append(page.page_number)
        markdown = "\n\n".join(
            f"<!-- page {p.page_number} -->\n{doc.export_to_markdown(page_no=p.page_number)}"
            for p in raw.pages)
        parsed = ParsedDocument(raw.pages, markdown,
                                {"parser": "docling", "ocr_pages": ocr_pages},
                                doc.export_to_dict())
        if self.artifact_dir is not None:
            target = self.artifact_dir / hashlib.sha256(content).hexdigest()
            target.mkdir(parents=True, exist_ok=True)
            (target / "source.pdf").write_bytes(content)
            (target / "document.md").write_text(markdown)
            (target / "document.json").write_text(json.dumps(parsed.structured, ensure_ascii=False))
            (target / "pages.json").write_text(json.dumps({
                "pages": [p.model_dump() for p in raw.pages], "provenance": parsed.provenance},
                ensure_ascii=False))
        return parsed


class FallbackDocumentParser(DocumentParser):
    def __init__(self, primary: DocumentParser, fallback: DocumentParser):
        self.primary, self.fallback = primary, fallback

    def parse(self, content: bytes) -> ParsedDocument:
        try:
            return self.primary.parse(content)
        except Exception as exc:
            log.warning("document parser failed (%s), using lightweight fallback",
                        type(exc).__name__)
            result = self.fallback.parse(content)
            result.provenance["fallback_warning"] = type(exc).__name__
            return result
