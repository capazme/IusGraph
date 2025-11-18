"""
Ingestion Pipeline
==================

Orchestrates the complete document ingestion workflow.

Workflow:
1. Read document → segments with provenance
2. Extract entities/relationships via LLM
3. Validate and enrich extractions
4. Write to Neo4j
5. Return statistics and report
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from neo4j import AsyncDriver

from .models import IngestionResult
from .document_reader import DocumentReader
from .llm_extractor import LLMExtractor
from .validator import Validator
from .neo4j_writer import Neo4jWriter

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Complete document ingestion pipeline.

    Coordinates all components to ingest documents into the knowledge graph.
    """

    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        openrouter_api_key: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ingestion pipeline.

        Args:
            neo4j_driver: Async Neo4j driver
            openrouter_api_key: OpenRouter API key for LLM
            config: Configuration dict (optional, uses defaults if not provided)
        """
        self.neo4j_driver = neo4j_driver
        self.config = config or {}
        self.logger = logger

        # Initialize components
        self.reader = DocumentReader(
            min_paragraph_words=self.config.get("reader", {}).get("paragraph_min_words", 10),
            context_chars=100,
        )

        llm_config = self.config.get("llm", {})
        self.extractor = LLMExtractor(
            api_key=openrouter_api_key,
            model=llm_config.get("model", "google/gemini-2.5-flash"),
            temperature=llm_config.get("temperature", 0.1),
            max_tokens=llm_config.get("max_tokens", 4000),
            timeout_seconds=llm_config.get("timeout_seconds", 60),
        )

        validation_config = self.config.get("validation", {})
        self.validator = Validator(
            strict_mode=validation_config.get("strict_mode", False),
            min_confidence=self.config.get("extraction", {}).get("confidence_threshold", 0.7),
        )

        writing_config = self.config.get("writing", {})
        self.writer = Neo4jWriter(
            neo4j_driver=neo4j_driver,
            batch_size=writing_config.get("batch_size", 100),
            duplicate_strategy=writing_config.get("duplicate_strategy", "merge"),
        )

    async def ingest_document(
        self,
        file_path: Path,
        auto_approve: bool = False,
        dry_run: bool = False,
        max_segments: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        prompt_override: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a document into the knowledge graph.

        Args:
            file_path: Path to document
            auto_approve: If True, write directly to Neo4j without staging
            dry_run: If True, extract but don't write to Neo4j
            max_segments: If set, only process first N segments (for testing)
            progress_callback: Optional function to report progress (step, message)
            prompt_override: Optional custom prompt template to use for extraction.

        Returns:
            IngestionResult with statistics and errors
        """
        file_path = Path(file_path)
        start_time = datetime.utcnow()

        def report_progress(step: int, message: str):
            if progress_callback:
                progress_callback(step, message)
            self.logger.info(message)

        report_progress(0, f"Starting ingestion of {file_path.name}")
        self.logger.info(f"Mode: auto_approve={auto_approve}, dry_run={dry_run}")

        result = IngestionResult(
            file_path=file_path,
            dry_run=dry_run,
        )

        try:
            # Step 1: Read document
            report_progress(1, "Step 1/5: Reading document...")
            segments = self.reader.read_document(file_path)

            if not segments:
                result.errors.append("No segments extracted from document")
                return result

            # Limit segments if requested (for testing)
            if max_segments:
                segments = segments[:max_segments]
                result.warnings.append(f"Limited to first {max_segments} segments for testing")

            result.segments_processed = len(segments)
            self.logger.info(f"Extracted {len(segments)} segments")

            # Step 2: Extract entities/relationships via LLM
            report_progress(2, "Step 2/5: Extracting entities and relationships via LLM...")

            max_concurrent = self.config.get("extraction", {}).get("parallel_requests", 3)
            extraction_results = await self.extractor.extract_batch(
                segments,
                max_concurrent=max_concurrent,
                prompt_template_override=prompt_override
            )

            # Calculate total entities and cost
            total_entities = sum(len(r.entities) for r in extraction_results)
            total_relationships = sum(len(r.relationships) for r in extraction_results)
            total_cost = sum(r.cost_usd for r in extraction_results)

            result.entities_extracted = total_entities
            result.cost_usd = total_cost

            self.logger.info(
                f"Extracted {total_entities} entities, "
                f"{total_relationships} relationships (cost: ${total_cost:.4f})"
            )

            # Check for extraction errors
            extraction_errors = [r.error for r in extraction_results if r.error]
            if extraction_errors:
                result.warnings.extend([f"Extraction error: {e}" for e in extraction_errors])

            # Step 3: Validate and enrich
            report_progress(3, "Step 3/5: Validating and enriching extractions...")
            validated_results = await self.validator.validate_and_enrich(extraction_results)

            # Step 4: Write to Neo4j (or skip if dry run)
            if dry_run:
                report_progress(4, "Step 4/5: Skipping write (dry run mode)")
                result.entities_written = 0
                result.relationships_created = 0
            else:
                report_progress(4, "Step 4/5: Writing to Neo4j...")
                write_stats = await self.writer.write_extraction_results(
                    validated_results,
                    dry_run=dry_run
                )

                result.entities_written = write_stats["nodes_created"]
                result.relationships_created = write_stats["relationships_created"]

                if write_stats["errors"]:
                    result.errors.extend(write_stats["errors"])

            # Step 5: Final statistics
            end_time = datetime.utcnow()
            result.duration_seconds = (end_time - start_time).total_seconds()

            result.metadata = {
                "model_used": self.extractor.model,
                "segments_total": len(segments),
                "segments_with_entities": sum(1 for r in extraction_results if r.entities),
                "average_confidence": self._calculate_average_confidence(extraction_results),
            }

            report_progress(5, "Step 5/5: Ingestion complete")
            self.logger.info(
                f"Summary: {result.entities_written} entities, "
                f"{result.relationships_created} relationships in {result.duration_seconds:.1f}s"
            )

        except Exception as e:
            self.logger.error(f"Critical error during ingestion: {e}", exc_info=True)
            result.errors.append(f"Critical error: {str(e)}")

            # Calculate duration even on error
            end_time = datetime.utcnow()
            result.duration_seconds = (end_time - start_time).total_seconds()

        return result

    def _calculate_average_confidence(self, extraction_results) -> float:
        """Calculate average confidence across all entities."""
        all_entities = []
        for result in extraction_results:
            all_entities.extend(result.entities)

        if not all_entities:
            return 0.0

        return sum(e.confidence for e in all_entities) / len(all_entities)

    async def ingest_directory(
        self,
        directory: Path,
        pattern: str = "*.pdf",
        **kwargs
    ) -> Dict[Path, IngestionResult]:
        """
        Ingest all documents in a directory.

        Args:
            directory: Directory containing documents
            pattern: Glob pattern for files (e.g., "*.pdf")
            **kwargs: Additional arguments passed to ingest_document()

        Returns:
            Dict mapping file paths to their ingestion results
        """
        directory = Path(directory)
        files = list(directory.glob(pattern))

        self.logger.info(f"Found {len(files)} files matching '{pattern}' in {directory}")

        results = {}
        for file_path in files:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing {file_path.name}")
            self.logger.info('='*60)

            result = await self.ingest_document(file_path, **kwargs)
            results[file_path] = result

            # Print summary for each file
            result.print_summary()

        # Print overall summary
        self.logger.info(f"\n{'='*60}")
        self.logger.info("BATCH INGESTION COMPLETE")
        self.logger.info('='*60)
        self.logger.info(f"Files processed: {len(results)}")
        self.logger.info(f"Total entities: {sum(r.entities_written for r in results.values())}")
        self.logger.info(f"Total cost: ${sum(r.cost_usd for r in results.values()):.4f}")

        return results
