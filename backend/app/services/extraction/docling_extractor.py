from __future__ import annotations

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.services.extraction.models import (
    ExtractionDocument,
    ExtractionOutput,
)

# Current extraction output contract for this stage:
# - response contains lightweight document metadata,
# - raw Docling output is exposed directly for debugging and test purposes,
# - no project-specific normalization or hierarchy-building is performed yet.
#
# This means the current extraction stage ends when Docling output is obtained.
# Structures such as page-based block streams or A -> A.1 -> A.1.1 -> 1-)
# hierarchy will be produced later by a separate parser/normalizer stage.


def extract_pdf_with_docling(file_path: str | Path) -> ExtractionOutput:
    # Main extractor entry point used by the service and API layers.
    #
    # Responsibilities of this function:
    # 1. run Docling on the uploaded PDF with our fixed pipeline settings,
    # 2. expose the raw Docling output for debugging and UI inspection,
    # 3. avoid any project-specific normalization or hierarchy logic for now.
    #
    # The final hierarchy such as A -> A.1 -> A.1.1 -> 1-) will be built by a
    # later parser stage. This extractor intentionally stops at Docling output.
    pdf_path = Path(file_path)
    converter = _build_docling_converter()
    conversion_result = converter.convert(str(pdf_path))
    docling_document = conversion_result.document
    docling_output = docling_document.model_dump()

    page_count = len(docling_output.get("pages", []))
    return ExtractionOutput(
        document=ExtractionDocument(
            file_name=pdf_path.name,
            page_count=page_count,
        ),
        docling_output=docling_output,
    )


def _build_docling_converter() -> DocumentConverter:
    # Docling pipeline configuration is intentionally strict:
    # - OCR disabled because project documents are selectable PDFs,
    # - table structure enabled because tables are first-class output,
    # - formula enrichment disabled because these proposal forms do not need it,
    # - backend text forced so selectable text is preferred,
    # - page image generation disabled because we do not use page renders.
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.do_formula_enrichment = False
    pipeline_options.force_backend_text = True
    pipeline_options.generate_page_images = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )
