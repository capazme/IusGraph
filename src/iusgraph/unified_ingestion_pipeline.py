# =============================================================================
# Unified Ingestion Pipeline - Multi-Source Legal Document Import
# =============================================================================
#
# This pipeline coordinates ingestion from multiple legal data sources:
#   1. Visualex (Codice Civile, Italian norms via Normattiva/EUR-Lex)
#   2. Normattiva API (direct government API integration)
#   3. Document Ingestion (PDF/DOCX manuali with LLM extraction)
#
# Architecture:
#   [Data Source] → [Parser/Client] → [Staging Queue] → [Quality Control] →
#   [Neo4j Writer] → [Validation]
#
# Quality Control Workflow:
#   - Confidence >0.90 + source=visualex → Auto-approve (official source)
#   - Confidence >0.85 + source=normattiva → Auto-approve
#   - Confidence >0.80 + source=PDF + entity_type=Norma → Auto-approve
#   - Confidence <threshold → Manual review (staging queue)
#
# Incremental Strategy:
#   Phase 1: 100 entities (manual review)
#   Phase 2: 1,000 entities (auto-approve pattern validated)
#   Phase 3: 5,000+ entities (production scale)
#
# =============================================================================

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import structlog

# Database imports
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update, delete, and_

# MERL-T imports
from .sources.visualex_client import VisualexClient, VisualexResponse
from .models_kg import StagingEntity, EntityTypeEnum, SourceTypeEnum
from .neo4j_graph_builder import Neo4jLegalKnowledgeGraph
from .document_ingestion.ingestion_pipeline import IngestionPipeline as DocumentIngestionPipeline

log = structlog.get_logger(__name__)


# =============================================================================
# Enums & Configuration
# =============================================================================

class IngestionSource(str, Enum):
    """Supported data sources for ingestion."""
    VISUALEX = "visualex"  # Codice Civile via visualex API
    NORMATTIVA = "normattiva"  # Direct Normattiva API
    DOCUMENTS = "documents"  # PDF/DOCX with LLM extraction
    COMMUNITY = "community"  # Community contributions


class IngestionMode(str, Enum):
    """Ingestion execution modes."""
    DRY_RUN = "dry_run"  # Extract only, no DB writes
    STAGING = "staging"  # Write to staging queue for review
    AUTO_APPROVE = "auto_approve"  # Auto-approve high-confidence entities
    PRODUCTION = "production"  # Full production import


@dataclass
class QualityControlConfig:
    """Quality control thresholds and rules."""
    # Confidence thresholds per source
    visualex_auto_approve_threshold: float = 0.95  # Official source, very high confidence
    normattiva_auto_approve_threshold: float = 0.90
    documents_norma_threshold: float = 0.85  # Structured norms in PDFs
    documents_default_threshold: float = 0.80  # General entities from PDFs

    # Review rules
    require_manual_review_below: float = 0.75  # Always manual review below this
    max_auto_approve_batch: int = 1000  # Max entities to auto-approve in single batch

    # Validation rules
    min_text_length: int = 10  # Minimum text length for entity
    max_text_length: int = 50000  # Maximum text length (anti-spam)


@dataclass
class IngestionConfig:
    """Pipeline configuration."""
    # Database
    database_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    # API endpoints
    visualex_url: str = "http://localhost:5000"
    normattiva_api_url: Optional[str] = None

    # LLM (for document ingestion)
    openrouter_api_key: Optional[str] = None
    llm_model: str = "google/gemini-2.5-flash"

    # Quality control
    quality_control: QualityControlConfig = field(default_factory=QualityControlConfig)

    # Batch processing
    batch_size: int = 50  # Entities per batch
    max_concurrent_requests: int = 3  # Parallel API requests

    # Modes
    ingestion_mode: IngestionMode = IngestionMode.STAGING
    dry_run: bool = False


# =============================================================================
# Ingestion Statistics
# =============================================================================

@dataclass
class IngestionStats:
    """Track ingestion pipeline statistics."""
    source: str
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    # Counts
    total_requested: int = 0
    total_fetched: int = 0
    total_staged: int = 0  # Written to staging queue
    total_approved: int = 0  # Auto-approved to Neo4j
    total_rejected: int = 0  # Quality control rejections
    total_errors: int = 0

    # Quality metrics
    avg_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0

    # Cost (for LLM-based sources)
    estimated_cost_usd: float = 0.0

    # Errors
    errors: List[str] = field(default_factory=list)

    def add_entity(
        self,
        confidence: float,
        approved: bool = False,
        rejected: bool = False,
        cost_usd: float = 0.0
    ):
        """Update stats with new entity."""
        self.total_fetched += 1
        if approved:
            self.total_approved += 1
        if rejected:
            self.total_rejected += 1
        else:
            self.total_staged += 1

        # Update confidence stats
        self.avg_confidence = (
            (self.avg_confidence * (self.total_fetched - 1) + confidence) /
            self.total_fetched
        )
        self.min_confidence = min(self.min_confidence, confidence)
        self.max_confidence = max(self.max_confidence, confidence)

        # Update cost
        self.estimated_cost_usd += cost_usd

    def finalize(self):
        """Mark ingestion as complete."""
        self.end_time = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/reporting."""
        return {
            'source': self.source,
            'duration_seconds': self.duration_seconds,
            'total_requested': self.total_requested,
            'total_fetched': self.total_fetched,
            'total_staged': self.total_staged,
            'total_approved': self.total_approved,
            'total_rejected': self.total_rejected,
            'total_errors': self.total_errors,
            'avg_confidence': round(self.avg_confidence, 3),
            'min_confidence': round(self.min_confidence, 3),
            'max_confidence': round(self.max_confidence, 3),
            'estimated_cost_usd': round(self.estimated_cost_usd, 2),
            'errors_count': len(self.errors)
        }


# =============================================================================
# Unified Ingestion Pipeline
# =============================================================================

class UnifiedIngestionPipeline:
    """
    Orchestrates multi-source ingestion with quality control.

    Features:
    - Coordinate 3 data sources (visualex, Normattiva, documents)
    - Staging queue for manual review
    - Confidence-based auto-approval
    - Incremental batch processing (100 → 1,000 → 5,000)
    - Progress tracking + cost estimation
    - Rollback on error
    """

    def __init__(self, config: IngestionConfig):
        """
        Initialize ingestion pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config

        # Database session factory
        self.engine = create_async_engine(
            config.database_url,
            echo=False,
            future=True
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Clients (lazy initialization)
        self._visualex_client: Optional[VisualexClient] = None
        self._neo4j_builder: Optional[Neo4jLegalKnowledgeGraph] = None
        self._document_pipeline: Optional[DocumentIngestionPipeline] = None

        log.info(
            "UnifiedIngestionPipeline initialized",
            mode=config.ingestion_mode.value,
            dry_run=config.dry_run
        )

    @property
    def visualex_client(self) -> VisualexClient:
        """Lazy-load visualex client."""
        if self._visualex_client is None:
            self._visualex_client = VisualexClient(base_url=self.config.visualex_url)
        return self._visualex_client

    @property
    def neo4j_builder(self) -> Neo4jLegalKnowledgeGraph:
        """Lazy-load Neo4j graph builder."""
        if self._neo4j_builder is None:
            self._neo4j_builder = Neo4jLegalKnowledgeGraph(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user,
                password=self.config.neo4j_password
            )
        return self._neo4j_builder

    # =========================================================================
    # Quality Control
    # =========================================================================

    def should_auto_approve(
        self,
        entity: Dict[str, Any],
        source: IngestionSource
    ) -> bool:
        """
        Determine if entity should be auto-approved based on confidence + source.

        Args:
            entity: Entity dictionary with 'confidence' and 'entity_type'
            source: Data source

        Returns:
            True if should auto-approve, False if manual review needed
        """
        confidence = entity.get('confidence', 0.0)
        entity_type = entity.get('entity_type')
        qc = self.config.quality_control

        # Always manual review below threshold
        if confidence < qc.require_manual_review_below:
            return False

        # Auto-approve rules per source
        if source == IngestionSource.VISUALEX:
            return confidence >= qc.visualex_auto_approve_threshold

        elif source == IngestionSource.NORMATTIVA:
            return confidence >= qc.normattiva_auto_approve_threshold

        elif source == IngestionSource.DOCUMENTS:
            # Higher threshold for structured norms
            if entity_type == 'Norma':
                return confidence >= qc.documents_norma_threshold
            else:
                return confidence >= qc.documents_default_threshold

        return False  # Default: manual review

    def validate_entity(self, entity: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate entity meets quality requirements.

        Args:
            entity: Entity dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        qc = self.config.quality_control
        props = entity.get('properties', {})

        # Check text length
        text = props.get('testo_completo', '') or props.get('text', '')
        if text:
            if len(text) < qc.min_text_length:
                return False, f"Text too short ({len(text)} chars < {qc.min_text_length})"
            if len(text) > qc.max_text_length:
                return False, f"Text too long ({len(text)} chars > {qc.max_text_length})"

        # Check required fields
        entity_type = entity.get('entity_type')
        if not entity_type:
            return False, "Missing entity_type"

        # Entity-specific validation
        if entity_type == 'Norma':
            if not props.get('numero_articolo') and not props.get('numero_atto'):
                return False, "Norma missing both numero_articolo and numero_atto"

        return True, None

    # =========================================================================
    # Staging Queue Management
    # =========================================================================

    async def write_to_staging(
        self,
        session: AsyncSession,
        entities: List[Dict[str, Any]],
        source: IngestionSource
    ) -> int:
        """
        Write entities to PostgreSQL staging queue for manual review.

        Args:
            session: Database session
            entities: List of entities to stage
            source: Data source

        Returns:
            Number of entities written
        """
        if self.config.dry_run:
            log.info("DRY RUN: Would write to staging", count=len(entities))
            return len(entities)

        written = 0
        for entity in entities:
            # Validate
            is_valid, error = self.validate_entity(entity)
            if not is_valid:
                log.warning("Entity validation failed", error=error)
                continue

            # Create staging entity
            staging_entity = StagingEntity(
                entity_type=EntityTypeEnum(entity['entity_type']),
                source_type=SourceTypeEnum[source.value.upper()],
                raw_data=entity,
                confidence_score=entity.get('confidence', 0.0),
                status='PENDING',
                created_at=datetime.utcnow()
            )

            session.add(staging_entity)
            written += 1

        await session.commit()
        log.info("Wrote entities to staging", count=written)
        return written

    async def get_pending_staging_entities(
        self,
        session: AsyncSession,
        limit: int = 100
    ) -> List[StagingEntity]:
        """
        Get pending entities from staging queue.

        Args:
            session: Database session
            limit: Max entities to retrieve

        Returns:
            List of pending staging entities
        """
        stmt = (
            select(StagingEntity)
            .where(StagingEntity.status == 'PENDING')
            .order_by(StagingEntity.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Source-Specific Ingestion
    # =========================================================================

    async def ingest_from_visualex(
        self,
        tipo_atto: str,
        articoli: List[str],
        progress_callback: Optional[Callable] = None
    ) -> IngestionStats:
        """
        Ingest articles from visualex API.

        Args:
            tipo_atto: Type of legal act (e.g., "codice civile")
            articoli: List of article numbers
            progress_callback: Optional callback(current, total)

        Returns:
            IngestionStats with results
        """
        stats = IngestionStats(source="visualex")
        stats.total_requested = len(articoli)

        log.info(
            "Starting visualex ingestion",
            tipo_atto=tipo_atto,
            articoli_count=len(articoli)
        )

        try:
            async with self.visualex_client as client:
                # Fetch articles
                response = await client.fetch_articles(
                    tipo_atto=tipo_atto,
                    articoli=articoli,
                    progress_callback=progress_callback
                )

                # Convert to Neo4j entities
                entities = [
                    norma_data.to_neo4j_entity()
                    for norma_data in response.data
                ]

                # Process entities
                async with self.SessionLocal() as session:
                    for entity in entities:
                        confidence = entity.get('confidence', 0.0)

                        # Auto-approve or stage?
                        if self.should_auto_approve(entity, IngestionSource.VISUALEX):
                            # Write directly to Neo4j
                            if not self.config.dry_run:
                                await self.neo4j_builder.create_node(
                                    entity['entity_type'],
                                    entity['properties']
                                )
                            stats.add_entity(confidence, approved=True)
                            log.debug("Auto-approved entity", entity_type=entity['entity_type'])

                        else:
                            # Stage for review
                            await self.write_to_staging(session, [entity], IngestionSource.VISUALEX)
                            stats.add_entity(confidence, approved=False)
                            log.debug("Staged entity for review", entity_type=entity['entity_type'])

                # Track errors
                stats.total_errors = len(response.errors)
                stats.errors = response.errors

        except Exception as e:
            log.error("visualex ingestion failed", error=str(e), exc_info=True)
            stats.errors.append(str(e))
            stats.total_errors += 1

        stats.finalize()
        log.info("visualex ingestion complete", stats=stats.to_dict())
        return stats

    async def ingest_codice_civile_batch(
        self,
        start_article: int,
        end_article: int,
        batch_size: int = 50,
        progress_callback: Optional[Callable] = None
    ) -> IngestionStats:
        """
        Convenience method to ingest sequential Codice Civile articles.

        Args:
            start_article: Starting article number (e.g., 1)
            end_article: Ending article number (inclusive, e.g., 2969)
            batch_size: Articles per batch
            progress_callback: Optional callback(current, total)

        Returns:
            IngestionStats with results
        """
        articoli = [str(i) for i in range(start_article, end_article + 1)]
        return await self.ingest_from_visualex(
            tipo_atto="codice civile",
            articoli=articoli,
            progress_callback=progress_callback
        )

    # TODO: Implement other sources
    # async def ingest_from_normattiva(self, ...):
    # async def ingest_from_documents(self, ...):

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self):
        """Close all connections."""
        if self._visualex_client:
            await self._visualex_client.close()
        if self._neo4j_builder:
            await self._neo4j_builder.close()
        await self.engine.dispose()
        log.info("UnifiedIngestionPipeline closed")


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """Test ingestion pipeline with sample Codice Civile articles."""
    import os

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    # Configuration
    config = IngestionConfig(
        database_url=os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/merl_t"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        visualex_url="http://localhost:5000",
        ingestion_mode=IngestionMode.STAGING,
        dry_run=True  # Safety: dry run for testing
    )

    log.info("Testing UnifiedIngestionPipeline")

    async with UnifiedIngestionPipeline(config) as pipeline:
        # Test: Ingest Codice Civile articles 1-10
        def progress(current, total):
            percent = (current / total) * 100
            print(f"\rProgress: {current}/{total} ({percent:.1f}%)", end='')

        stats = await pipeline.ingest_codice_civile_batch(
            start_article=1,
            end_article=10,
            batch_size=5,
            progress_callback=progress
        )

        print()  # Newline
        print("\n" + "=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)
        print(f"  Total requested: {stats.total_requested}")
        print(f"  Total fetched: {stats.total_fetched}")
        print(f"  Total staged: {stats.total_staged}")
        print(f"  Total approved: {stats.total_approved}")
        print(f"  Total errors: {stats.total_errors}")
        print(f"  Avg confidence: {stats.avg_confidence:.3f}")
        print(f"  Duration: {stats.duration_seconds:.1f}s")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
