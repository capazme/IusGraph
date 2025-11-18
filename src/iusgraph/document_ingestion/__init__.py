"""
Document Ingestion Package
===========================

LLM-based pipeline for ingesting legal documents (PDF/DOCX/TXT) into
the MERL-T Knowledge Graph.

Components:
- DocumentReader: Extract text with provenance from documents
- LLMExtractor: Use LLM to extract entities/relationships per KG schema
- Validator: Validate and enrich extractions
- Neo4jWriter: Write to Neo4j with full KG schema support
- IngestionPipeline: Orchestrate the complete workflow

Usage:
    from backend.preprocessing.document_ingestion import IngestionPipeline

    pipeline = IngestionPipeline(
        neo4j_driver=driver,
        config=config
    )

    result = await pipeline.ingest_document(
        file_path="manual.pdf",
        auto_approve=True
    )

    print(f"Extracted {result.entities_extracted} entities")
"""

from .models import (
    Provenance,
    DocumentSegment,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    IngestionResult,
)
from .document_reader import DocumentReader
from .llm_extractor import LLMExtractor
from .validator import Validator
from .neo4j_writer import Neo4jWriter
from .ingestion_pipeline import IngestionPipeline

__all__ = [
    # Data Models
    "Provenance",
    "DocumentSegment",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionResult",
    "IngestionResult",
    # Components
    "DocumentReader",
    "LLMExtractor",
    "Validator",
    "Neo4jWriter",
    "IngestionPipeline",
]
