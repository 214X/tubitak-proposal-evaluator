from __future__ import annotations

from app.services.chunking import build_chunk_output
from app.services.chunking.models import ChunkOutput
from app.services.extraction.models import ParserOutput
from app.services.extraction.service import get_current_parser_output


def build_chunk_output_from_parser(parser_output: ParserOutput) -> ChunkOutput:
    # Chunking consumes parser output directly. This keeps the pipeline staged:
    # extraction -> parser -> chunking. The chunking layer should not need to
    # know how extraction happened as long as parser output is already present.
    return build_chunk_output(
        document_id=parser_output.document["file_name"],
        content_stream=parser_output.content_stream,
        heading_hierarchy=parser_output.heading_hierarchy,
    )


def get_current_chunk_output(session_id: str) -> ChunkOutput:
    # Keep a session-based convenience wrapper for API callers, but route the
    # real work through the parser-output entrypoint above.
    parser_output = get_current_parser_output(session_id)
    return build_chunk_output_from_parser(parser_output)
