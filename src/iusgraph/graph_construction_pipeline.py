# =============================================================================
# Graph Construction Pipeline - LLM-Driven KG Builder
# =============================================================================
#
# This pipeline combines:
# 1. visualex client (fetch articles + BrocardiInfo)
# 2. LLM Graph Extractor (extract entities + relationships)
# 3. Unified Ingestion Pipeline (staging + quality control)
# 4. Neo4j writer (approved entities/relationships → graph)
#
# Workflow:
# 1. Fetch article from visualex (text + BrocardiInfo)
# 2. LLM analyzes → extracts entities + relationships
# 3. Entities/relationships → staging queue (PostgreSQL)
# 4. User reviews → approves/rejects
# 5. Approved → written to Neo4j KG
# 6. Patterns learned → progressive auto-approval
#
# You (user) are the first validator. Your approvals train the system.
#
# =============================================================================

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import structlog

# MERL-T imports
from .sources.visualex_client import VisualexClient, NormaData
from .llm_graph_extractor import LLMGraphExtractor, GraphExtractionResult
from .unified_ingestion_pipeline import (
    UnifiedIngestionPipeline,
    IngestionConfig,
    IngestionStats,
    IngestionSource
)

log = structlog.get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class GraphConstructionConfig:
    """Configuration for graph construction pipeline."""

    # API keys
    openrouter_api_key: str
    visualex_url: str = "http://localhost:5000"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/merl_t"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # LLM
    llm_model: str = "google/gemini-2.5-flash"
    llm_temperature: float = 0.1

    # Processing
    include_brocardi: bool = True  # Fetch BrocardiInfo enrichment
    batch_size: int = 10  # Articles per batch
    max_concurrent_llm: int = 3  # Parallel LLM calls

    # Quality control (auto-approval thresholds)
    entity_auto_approve_threshold: float = 0.85
    relationship_auto_approve_threshold: float = 0.80

    # Modes
    dry_run: bool = False
    review_mode: str = "manual"  # "manual" or "auto"


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class GraphConstructionStats:
    """Track pipeline statistics."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    # Articles processed
    articles_requested: int = 0
    articles_fetched: int = 0
    articles_processed: int = 0

    # Entities
    total_entities_extracted: int = 0
    entities_staged: int = 0
    entities_auto_approved: int = 0
    entities_manual_review: int = 0

    # Relationships
    total_relationships_extracted: int = 0
    relationships_staged: int = 0
    relationships_auto_approved: int = 0
    relationships_manual_review: int = 0

    # Quality
    avg_entity_confidence: float = 0.0
    avg_relationship_confidence: float = 0.0

    # Cost
    total_llm_cost_usd: float = 0.0

    # Errors
    errors: List[str] = field(default_factory=list)

    def finalize(self):
        """Mark processing complete."""
        self.end_time = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for reporting."""
        return {
            'duration_seconds': self.duration_seconds,
            'articles': {
                'requested': self.articles_requested,
                'fetched': self.articles_fetched,
                'processed': self.articles_processed,
            },
            'entities': {
                'total_extracted': self.total_entities_extracted,
                'staged': self.entities_staged,
                'auto_approved': self.entities_auto_approved,
                'manual_review': self.entities_manual_review,
                'avg_confidence': round(self.avg_entity_confidence, 3),
            },
            'relationships': {
                'total_extracted': self.total_relationships_extracted,
                'staged': self.relationships_staged,
                'auto_approved': self.relationships_auto_approved,
                'manual_review': self.relationships_manual_review,
                'avg_confidence': round(self.avg_relationship_confidence, 3),
            },
            'cost_usd': round(self.total_llm_cost_usd, 2),
            'errors_count': len(self.errors)
        }


# =============================================================================
# Graph Construction Pipeline
# =============================================================================

class GraphConstructionPipeline:
    """
    End-to-end pipeline for LLM-driven knowledge graph construction.

    Coordinates:
    - visualex (fetch articles)
    - LLM extractor (extract entities/relationships)
    - Staging queue (manual review)
    - Neo4j writer (approved items)
    """

    def __init__(self, config: GraphConstructionConfig):
        """
        Initialize pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.stats = GraphConstructionStats()

        # Initialize components
        self.visualex_client = VisualexClient(base_url=config.visualex_url)
        self.llm_extractor = LLMGraphExtractor(
            openrouter_api_key=config.openrouter_api_key,
            model=config.llm_model,
            temperature=config.llm_temperature
        )

        # Ingestion pipeline config
        ingestion_config = IngestionConfig(
            database_url=config.database_url,
            neo4j_uri=config.neo4j_uri,
            neo4j_user=config.neo4j_user,
            neo4j_password=config.neo4j_password,
            visualex_url=config.visualex_url,
            openrouter_api_key=config.openrouter_api_key,
            dry_run=config.dry_run
        )
        self.ingestion_pipeline = UnifiedIngestionPipeline(ingestion_config)

        log.info(
            "GraphConstructionPipeline initialized",
            llm_model=config.llm_model,
            include_brocardi=config.include_brocardi,
            review_mode=config.review_mode
        )

    async def construct_graph_from_articles(
        self,
        tipo_atto: str,
        articoli: List[str],
        progress_callback: Optional[callable] = None
    ) -> GraphConstructionStats:
        """
        Construct knowledge graph from list of articles.

        Args:
            tipo_atto: Type of act (e.g., "codice civile")
            articoli: List of article numbers (e.g., ["2043", "2044"])
            progress_callback: Optional callback(current, total)

        Returns:
            GraphConstructionStats with results
        """
        self.stats.articles_requested = len(articoli)

        log.info(
            "Starting graph construction",
            tipo_atto=tipo_atto,
            articles_count=len(articoli),
            include_brocardi=self.config.include_brocardi
        )

        try:
            # Step 1: Fetch articles from visualex
            log.info("Step 1: Fetching articles from visualex")
            if self.config.include_brocardi:
                response = await self.visualex_client.fetch_articles_with_brocardi(
                    tipo_atto=tipo_atto,
                    articoli=articoli
                )
            else:
                response = await self.visualex_client.fetch_articles(
                    tipo_atto=tipo_atto,
                    articoli=articoli
                )

            self.stats.articles_fetched = len(response.data)
            log.info(f"Fetched {self.stats.articles_fetched} articles")

            # Step 2: Process each article with LLM
            log.info("Step 2: Extracting entities/relationships with LLM")

            entity_confidences = []
            relationship_confidences = []

            for idx, norma_data in enumerate(response.data):
                log.info(
                    f"Processing article {idx + 1}/{len(response.data)}",
                    article=norma_data.numero_articolo
                )

                # Extract graph from article
                extraction_result = await self._extract_graph_from_article(norma_data)

                # Update stats
                self.stats.total_entities_extracted += extraction_result.total_entities
                self.stats.total_relationships_extracted += extraction_result.total_relationships
                self.stats.total_llm_cost_usd += extraction_result.llm_cost_usd
                self.stats.articles_processed += 1

                # Collect confidences for averaging
                for entity in extraction_result.entities:
                    entity_confidences.append(entity.confidence)
                for rel in extraction_result.relationships:
                    relationship_confidences.append(rel.confidence)

                # Step 3: Stage entities/relationships for review
                await self._stage_extraction_result(extraction_result, norma_data)

                # Progress callback
                if progress_callback:
                    await progress_callback(idx + 1, len(response.data))

            # Calculate averages
            if entity_confidences:
                self.stats.avg_entity_confidence = sum(entity_confidences) / len(entity_confidences)
            if relationship_confidences:
                self.stats.avg_relationship_confidence = sum(relationship_confidences) / len(relationship_confidences)

        except Exception as e:
            log.error("Graph construction failed", error=str(e), exc_info=True)
            self.stats.errors.append(str(e))

        self.stats.finalize()
        log.info("Graph construction complete", stats=self.stats.to_dict())
        return self.stats

    async def construct_codice_civile_batch(
        self,
        start_article: int,
        end_article: int,
        progress_callback: Optional[callable] = None
    ) -> GraphConstructionStats:
        """
        Convenience method for Codice Civile batch processing.

        Args:
            start_article: Starting article number
            end_article: Ending article number (inclusive)
            progress_callback: Optional callback(current, total)

        Returns:
            GraphConstructionStats
        """
        articoli = [str(i) for i in range(start_article, end_article + 1)]
        return await self.construct_graph_from_articles(
            tipo_atto="codice civile",
            articoli=articoli,
            progress_callback=progress_callback
        )

    async def _extract_graph_from_article(
        self,
        norma_data: NormaData
    ) -> GraphExtractionResult:
        """
        Extract graph from a single article using LLM.

        Args:
            norma_data: Article data from visualex

        Returns:
            GraphExtractionResult
        """
        # Prepare BrocardiInfo dict (if available)
        brocardi_dict = None
        if norma_data.brocardi_info:
            brocardi_dict = {
                'position': norma_data.brocardi_info.position,
                'brocardi': norma_data.brocardi_info.brocardi,
                'ratio': norma_data.brocardi_info.ratio,
                'spiegazione': norma_data.brocardi_info.spiegazione,
                'massime': norma_data.brocardi_info.massime
            }

        # Call LLM extractor
        result = await self.llm_extractor.extract_graph(
            article_text=norma_data.article_text,
            article_number=norma_data.numero_articolo,
            brocardi_info=brocardi_dict
        )

        return result

    async def _stage_extraction_result(
        self,
        extraction_result: GraphExtractionResult,
        source_norma: NormaData
    ):
        """
        Stage extraction result (entities + relationships) for review.

        Args:
            extraction_result: LLM extraction result
            source_norma: Source article data
        """
        from .models_kg import StagingEntity, StagingRelationship, EntityTypeEnum, SourceTypeEnum
        from sqlalchemy.ext.asyncio import AsyncSession

        if self.config.dry_run:
            log.info(
                "DRY RUN: Would stage extraction",
                entities=extraction_result.total_entities,
                relationships=extraction_result.total_relationships
            )
            return

        async with self.ingestion_pipeline.SessionLocal() as session:
            # Stage entities
            for entity in extraction_result.entities:
                # Auto-approve or manual review?
                if entity.confidence >= self.config.entity_auto_approve_threshold:
                    # TODO: Write directly to Neo4j
                    self.stats.entities_auto_approved += 1
                    log.debug(
                        "Auto-approved entity",
                        entity_type=entity.entity_type,
                        confidence=entity.confidence
                    )
                else:
                    # Stage for manual review
                    staging_entity = StagingEntity(
                        entity_type=EntityTypeEnum(entity.entity_type) if hasattr(EntityTypeEnum, entity.entity_type) else EntityTypeEnum.CONTRIBUTION,
                        source_type=SourceTypeEnum.VISUALEX,
                        raw_data=entity.to_staging_dict(),
                        confidence_score=entity.confidence,
                        status='PENDING',
                        metadata={
                            'source_article': source_norma.numero_articolo,
                            'source_urn': source_norma.urn,
                            'llm_model': self.config.llm_model
                        },
                        created_at=datetime.utcnow()
                    )
                    session.add(staging_entity)
                    self.stats.entities_staged += 1
                    self.stats.entities_manual_review += 1

            # Stage relationships
            for relationship in extraction_result.relationships:
                # Auto-approve or manual review?
                if relationship.confidence >= self.config.relationship_auto_approve_threshold:
                    # TODO: Write directly to Neo4j
                    self.stats.relationships_auto_approved += 1
                    log.debug(
                        "Auto-approved relationship",
                        type=relationship.relationship_type,
                        confidence=relationship.confidence
                    )
                else:
                    # Stage for manual review
                    # TODO: Create StagingRelationship model
                    # For now, store in metadata of staging entity
                    self.stats.relationships_staged += 1
                    self.stats.relationships_manual_review += 1

            await session.commit()

            log.info(
                "Staged extraction result",
                entities_staged=self.stats.entities_staged,
                entities_auto_approved=self.stats.entities_auto_approved,
                relationships_staged=self.stats.relationships_staged,
                relationships_auto_approved=self.stats.relationships_auto_approved
            )

    async def close(self):
        """Close all connections."""
        await self.visualex_client.close()
        await self.ingestion_pipeline.close()
        log.info("GraphConstructionPipeline closed")


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """Test graph construction pipeline with sample articles."""
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
    config = GraphConstructionConfig(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        database_url=os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/merl_t"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        include_brocardi=True,
        dry_run=True,  # Safety
        review_mode="manual"
    )

    log.info("Testing GraphConstructionPipeline")

    pipeline = GraphConstructionPipeline(config)

    # Test: Process articles 2043-2045 (3 articles)
    def progress(current, total):
        percent = (current / total) * 100
        print(f"\rProgress: {current}/{total} ({percent:.1f}%)", end='')

    stats = await pipeline.construct_codice_civile_batch(
        start_article=2043,
        end_article=2045,
        progress_callback=progress
    )

    print()  # Newline
    print("\n" + "=" * 60)
    print("GRAPH CONSTRUCTION COMPLETE")
    print("=" * 60)
    print(f"\nArticles:")
    print(f"  Requested: {stats.articles_requested}")
    print(f"  Fetched: {stats.articles_fetched}")
    print(f"  Processed: {stats.articles_processed}")
    print(f"\nEntities:")
    print(f"  Total extracted: {stats.total_entities_extracted}")
    print(f"  Auto-approved: {stats.entities_auto_approved}")
    print(f"  Manual review: {stats.entities_manual_review}")
    print(f"  Avg confidence: {stats.avg_entity_confidence:.2f}")
    print(f"\nRelationships:")
    print(f"  Total extracted: {stats.total_relationships_extracted}")
    print(f"  Auto-approved: {stats.relationships_auto_approved}")
    print(f"  Manual review: {stats.relationships_manual_review}")
    print(f"  Avg confidence: {stats.avg_relationship_confidence:.2f}")
    print(f"\nCost: ${stats.total_llm_cost_usd:.2f}")
    print(f"Duration: {stats.duration_seconds:.1f}s")
    print("=" * 60 + "\n")

    await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
