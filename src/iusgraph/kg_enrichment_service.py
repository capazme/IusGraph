"""
Knowledge Graph Enrichment Service
===================================

Multi-source context enrichment for intent classification results.

Integrates:
- Norms (from Normattiva)
- Case law (from official registries)
- Doctrine (curated + community)
- Community contributions

Features:
- Redis caching (24h TTL)
- Dynamic quorum RLCF integration
- Multi-source Cypher queries
- Controversy flagging
- Audit trail tracking

Reference: docs/02-methodology/knowledge-graph.md
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from hashlib import md5
from enum import Enum
import asyncio

from neo4j import AsyncDriver, AsyncSession
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from pydantic import BaseModel, Field

# Import from query_understanding (unified interface - Week 7)
from .query_understanding import QueryUnderstandingResult, QueryIntentType
try:
    from .config.kg_config import KGConfig
except ImportError:
    # Fallback if config not available
    KGConfig = None

logger = logging.getLogger(__name__)


# ==========================================
# Data Models
# ==========================================

class NormaContext(BaseModel):
    """Context about a norm (Norma node)."""
    estremi: str = Field(..., description="Official identifier (e.g., 'Art. 1414 c.c.')")
    titolo: str = Field(..., description="Official title")
    descrizione: str = Field(..., description="Brief description")
    stato: str = Field(..., description="Status: vigente, abrogato, sospeso, modificato")
    testo_vigente: str = Field(..., description="Current text")
    data_entrata_in_vigore: str = Field(..., description="Date norm came into force")
    confidence: float = Field(default=1.0, description="Confidence score")
    source: str = Field(default="normattiva", description="Source (normattiva, rlcf, etc)")
    has_controversy: bool = Field(default=False, description="Whether norm is flagged controversial")

    class Config:
        schema_extra = {
            "example": {
                "estremi": "Art. 2043 c.c.",
                "titolo": "Risarcimento dei danni",
                "stato": "vigente",
                "confidence": 1.0,
                "source": "normattiva"
            }
        }


class SentenzaContext(BaseModel):
    """Context about a judicial act (sentenza)."""
    numero: str = Field(..., description="Case number (e.g., '1234/2023')")
    data: str = Field(..., description="Decision date")
    organo: str = Field(..., description="Issuing body (e.g., 'Cassazione')")
    materia: str = Field(..., description="Subject matter")
    norme_citate: List[str] = Field(default=[], description="Referenced norms")
    relation_type: str = Field(default="APPLICA", description="APPLICA or INTERPRETA")
    confidence: float = Field(default=0.85, description="Expert-assigned confidence")
    source: str = Field(default="cassazione", description="Source registry")
    has_errata_corrige: bool = Field(default=False, description="Whether sentenza has corrections")

    class Config:
        schema_extra = {
            "example": {
                "numero": "1234/2023",
                "organo": "Cassazione",
                "relation_type": "APPLICA",
                "confidence": 0.90,
                "source": "cassazione"
            }
        }


class DoctrineContext(BaseModel):
    """Context about doctrine (commentary/academic sources)."""
    titolo: str = Field(..., description="Title of doctrine text")
    autore: str = Field(..., description="Author(s)")
    fonte: str = Field(..., description="Source (journal, book, etc)")
    anno_pubblicazione: int = Field(..., description="Publication year")
    tipo_commento: str = Field(
        default="interpretativo",
        description="Type: interpretativo, critico, applicativo, sistematico"
    )
    citations_count: int = Field(default=0, description="# papers citing this")
    confidence: float = Field(default=0.75, description="Expert-assigned confidence")
    source_quality: str = Field(default="curated", description="curated or community_voted")

    class Config:
        schema_extra = {
            "example": {
                "titolo": "Responsabilità extracontrattuale",
                "autore": "Bianca",
                "fonte": "Diritto Civile",
                "anno_pubblicazione": 2020,
                "tipo_commento": "interpretativo",
                "confidence": 0.90,
                "source_quality": "curated"
            }
        }


class ContributionContext(BaseModel):
    """Context about community contribution."""
    author_id: str = Field(..., description="Contributor ID")
    titolo: str = Field(..., description="Contribution title")
    tipo: str = Field(..., description="Type: academic_paper, commentary, case_analysis, practice_guide")
    upvote_count: int = Field(default=0, description="Community upvotes")
    downvote_count: int = Field(default=0, description="Community downvotes")
    submission_date: str = Field(..., description="When submitted")
    confidence: float = Field(default=0.60, description="Based on community votes")
    expert_reviewed: bool = Field(default=False, description="Whether expert has reviewed")

    class Config:
        schema_extra = {
            "example": {
                "author_id": "user_123",
                "titolo": "Analisi pratica dell'Art. 2043",
                "tipo": "case_analysis",
                "upvote_count": 15,
                "confidence": 0.75,
                "expert_reviewed": True
            }
        }


class ControversyFlag(BaseModel):
    """Flag indicating contested/controversial data."""
    has_flag: bool = Field(default=False, description="Whether controversy exists")
    votes_conflicting: Dict[str, int] = Field(
        default={},
        description="Conflicting votes (e.g., {vigente: 10, abrogato_di_fatto: 95})"
    )
    authority_avg: float = Field(default=0.0, description="Average authority of conflicting votes")
    last_flagged: Optional[str] = Field(default=None, description="When flagged")
    notes: str = Field(default="", description="Explanation of controversy")


class EnrichedContext(BaseModel):
    """Complete enriched context from KG for expert modules."""
    query_understanding: QueryUnderstandingResult = Field(..., description="Original query understanding result")
    norms: List[NormaContext] = Field(default=[], description="Related norms")
    sentenze: List[SentenzaContext] = Field(default=[], description="Related case law")
    dottrina: List[DoctrineContext] = Field(default=[], description="Academic commentary")
    contributions: List[ContributionContext] = Field(default=[], description="Community insights")
    controversy_flags: List[ControversyFlag] = Field(default=[], description="Controversial items")
    enrichment_metadata: Dict[str, Any] = Field(
        default={},
        description="Metadata: cache_hit, query_time_ms, sources_queried"
    )
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        schema_extra = {
            "example": {
                "query_understanding": {
                    "query_id": "qu_123",
                    "intent": "norm_search",
                    "intent_confidence": 0.92
                },
                "norms": [],
                "sentenze": [],
                "enrichment_metadata": {
                    "cache_hit": False,
                    "query_time_ms": 245,
                    "sources_queried": ["normattiva", "cassazione"]
                }
            }
        }


# ==========================================
# KG Enrichment Service
# ==========================================

class KGEnrichmentService:
    """
    Enriches intent classification results with multi-source legal context.

    Features:
    - Queries Neo4j for related norms, sentenze, dottrina, contributions
    - Caches enriched context in Redis (24h TTL)
    - Tracks source provenance and confidence scores
    - Handles controversy flags from RLCF feedback
    - Supports all 4 intent types with custom query patterns
    """

    def __init__(
        self,
        neo4j_driver: Optional[AsyncDriver] = None,
        redis_client: Optional[AsyncRedis] = None,
        config: Optional[KGConfig] = None
    ):
        """
        Initialize KG enrichment service.

        Args:
            neo4j_driver: Neo4j async driver (optional, uses default if None)
            redis_client: Redis async client (optional, disables caching if None)
            config: KG configuration (optional, uses defaults if None)
        """
        self.neo4j_driver = neo4j_driver
        self.redis = redis_client
        self.config = config
        self.logger = logger

        # Graceful degradation flags
        self.neo4j_available = neo4j_driver is not None
        self.redis_available = redis_client is not None

        if not self.neo4j_available:
            self.logger.warning("Neo4j driver not provided - KG enrichment will be limited")
        if not self.redis_available:
            self.logger.warning("Redis client not provided - caching disabled")

    # ==========================================
    # Main Enrichment Method
    # ==========================================

    async def enrich_context(self, query_understanding: QueryUnderstandingResult) -> EnrichedContext:
        """
        Main method: enrich query understanding with KG context.

        Args:
            query_understanding: Result from query understanding module

        Returns:
            EnrichedContext with all related legal information

        Raises:
            ValueError: If intent type not supported
        """
        start_time = datetime.utcnow()

        try:
            # Graceful degradation: if Neo4j not available, return empty context
            if not self.neo4j_available:
                self.logger.warning("Neo4j unavailable - returning empty enriched context")
                return EnrichedContext(
                    query_understanding=query_understanding,
                    norms=[],
                    sentenze=[],
                    dottrina=[],
                    contributions=[],
                    controversy_flags=[],
                    enrichment_metadata={
                        "cache_hit": False,
                        "query_time_ms": 0,
                        "sources_queried": [],
                        "degraded_mode": True,
                        "reason": "neo4j_unavailable"
                    }
                )

            # Generate cache key from intent + concept
            cache_key = self._generate_cache_key(query_understanding)

            # Try Redis cache first (if available)
            if self.redis_available:
                cached = await self._get_from_cache(cache_key)
                if cached:
                    self.logger.debug(f"Cache HIT for {cache_key}")
                    enriched = EnrichedContext(**cached)
                    enriched.enrichment_metadata["cache_hit"] = True
                    return enriched

            self.logger.debug(f"Cache {'MISS' if self.redis_available else 'DISABLED'} for {cache_key}, querying Neo4j...")

            # Query Neo4j for all sources in parallel
            norms, sentenze, dottrina, contributions, controversies = await asyncio.gather(
                self._query_related_norms(query_understanding),
                self._query_related_sentenze(query_understanding),
                self._query_doctrine(query_understanding),
                self._query_contributions(query_understanding),
                self._query_controversy_flags(query_understanding)
            )

            # Build enriched context
            enriched = EnrichedContext(
                query_understanding=query_understanding,
                norms=norms,
                sentenze=sentenze,
                dottrina=dottrina,
                contributions=contributions,
                controversy_flags=controversies,
                enrichment_metadata={
                    "cache_hit": False,
                    "query_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "sources_queried": [
                        "normattiva" if norms else None,
                        "cassazione" if sentenze else None,
                        "dottrina" if dottrina else None,
                        "contributions" if contributions else None
                    ]
                }
            )

            # Cache result for 24h
            await self._cache_result(cache_key, enriched.dict())

            self.logger.info(
                f"Enrichment complete: {len(norms)} norms, {len(sentenze)} sentenze, "
                f"{len(dottrina)} doctrine, {len(contributions)} contributions"
            )

            return enriched

        except Exception as e:
            self.logger.error(f"Error enriching context: {str(e)}", exc_info=True)
            raise

    # ==========================================
    # Query Methods (Intent-Specific)
    # ==========================================

    async def _query_related_norms(self, query_understanding: QueryUnderstandingResult) -> List[NormaContext]:
        """Query norms related to query understanding."""
        try:
            async with self.neo4j_driver.session() as session:
                # Intent-specific query patterns (using QueryIntentType)
                if query_understanding.intent == QueryIntentType.INTERPRETATION:
                    query = """
                    MATCH (c:ConceptoGiuridico)-[:APPLICA_A]->(n:Norma)
                    WHERE c.nome CONTAINS $concept OR n.descrizione CONTAINS $concept
                    RETURN n.estremi as estremi, n.titolo as titolo, n.descrizione as descrizione,
                           n.stato as stato, n.testo_vigente as testo_vigente,
                           n.data_entrata_in_vigore as data_entrata_in_vigore,
                           n.controversy_flag as has_controversy
                    ORDER BY n.confidence DESC
                    LIMIT 10
                    """
                elif query_understanding.intent == QueryIntentType.COMPLIANCE_CHECK:
                    query = """
                    MATCH (n:Norma)-[:IMPONE]->(m:ModalitaGiuridica)
                    WHERE m.tipo_modalita IN ['obbligo', 'divieto']
                    AND (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
                    RETURN n.estremi as estremi, n.titolo as titolo, n.descrizione as descrizione,
                           n.stato as stato, n.testo_vigente as testo_vigente,
                           n.data_entrata_in_vigore as data_entrata_in_vigore,
                           n.controversy_flag as has_controversy
                    ORDER BY m.tipo_modalita DESC
                    LIMIT 10
                    """
                elif query_understanding.intent == QueryIntentType.NORM_SEARCH:
                    query = """
                    MATCH (n:Norma)-[:ESPRIME_PRINCIPIO]->(p:PrincipioGiuridico)
                    WHERE p.nome CONTAINS $concept OR n.descrizione CONTAINS $concept
                    RETURN n.estremi as estremi, n.titolo as titolo, n.descrizione as descrizione,
                           n.stato as stato, n.testo_vigente as testo_vigente,
                           n.data_entrata_in_vigore as data_entrata_in_vigore,
                           n.controversy_flag as has_controversy
                    ORDER BY p.livello DESC
                    LIMIT 10
                    """
                else:  # DOCUMENT_DRAFTING, RISK_SPOTTING, UNKNOWN
                    query = """
                    MATCH (n:Norma)
                    WHERE n.estremi CONTAINS $concept OR n.descrizione CONTAINS $concept
                    RETURN n.estremi as estremi, n.titolo as titolo, n.descrizione as descrizione,
                           n.stato as stato, n.testo_vigente as testo_vigente,
                           n.data_entrata_in_vigore as data_entrata_in_vigore,
                           n.controversy_flag as has_controversy
                    ORDER BY n.confidence DESC
                    LIMIT 10
                    """

                result = await session.run(
                    query,
                    concept=query_understanding.original_query or ""
                )

                norms = []
                async for record in result:
                    norms.append(NormaContext(
                        estremi=record["estremi"],
                        titolo=record["titolo"],
                        descrizione=record["descrizione"],
                        stato=record["stato"],
                        testo_vigente=record["testo_vigente"],
                        data_entrata_in_vigore=record["data_entrata_in_vigore"],
                        has_controversy=record.get("has_controversy", False)
                    ))

                return norms

        except Exception as e:
            self.logger.error(f"Error querying norms: {str(e)}", exc_info=True)
            return []

    async def _query_related_sentenze(self, query_understanding: QueryUnderstandingResult) -> List[SentenzaContext]:
        """Query case law (sentenze) related to query understanding."""
        try:
            async with self.neo4j_driver.session() as session:
                query = """
                MATCH (a:AttoGiudiziario)-[r:INTERPRETA|APPLICA]->(n:Norma)
                WHERE n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept
                RETURN a.numero as numero, a.data as data, a.organo as organo,
                       a.materia as materia, r.tipo as relation_type, r.confidence as confidence,
                       a.has_errata_corrige as has_errata_corrige
                ORDER BY a.data DESC
                LIMIT 5
                """

                result = await session.run(query, concept=query_understanding.original_query or "")

                sentenze = []
                async for record in result:
                    sentenze.append(SentenzaContext(
                        numero=record["numero"],
                        data=record["data"],
                        organo=record["organo"],
                        materia=record["materia"],
                        relation_type=record.get("relation_type", "APPLICA"),
                        confidence=record.get("confidence", 0.85),
                        has_errata_corrige=record.get("has_errata_corrige", False)
                    ))

                return sentenze

        except Exception as e:
            self.logger.error(f"Error querying sentenze: {str(e)}", exc_info=True)
            return []

    async def _query_doctrine(self, query_understanding: QueryUnderstandingResult) -> List[DoctrineContext]:
        """Query academic doctrine (commentaries)."""
        try:
            async with self.neo4j_driver.session() as session:
                query = """
                MATCH (d:Dottrina)-[r:COMMENTA]->(n:Norma)
                WHERE n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept
                RETURN d.titolo as titolo, d.autore as autore, d.fonte as fonte,
                       d.anno_pubblicazione as anno_pubblicazione,
                       r.tipo_commento as tipo_commento,
                       d.citations_count as citations_count,
                       r.confidence as confidence,
                       d.source_quality as source_quality
                ORDER BY d.citations_count DESC
                LIMIT 5
                """

                result = await session.run(query, concept=query_understanding.original_query or "")

                dottrina = []
                async for record in result:
                    dottrina.append(DoctrineContext(
                        titolo=record["titolo"],
                        autore=record["autore"],
                        fonte=record["fonte"],
                        anno_pubblicazione=record["anno_pubblicazione"],
                        tipo_commento=record.get("tipo_commento", "interpretativo"),
                        citations_count=record.get("citations_count", 0),
                        confidence=record.get("confidence", 0.75),
                        source_quality=record.get("source_quality", "curated")
                    ))

                return dottrina

        except Exception as e:
            self.logger.error(f"Error querying doctrine: {str(e)}", exc_info=True)
            return []

    async def _query_contributions(self, query_understanding: QueryUnderstandingResult) -> List[ContributionContext]:
        """Query community contributions."""
        try:
            async with self.neo4j_driver.session() as session:
                query = """
                MATCH (c:Contribution)-[r:INTERPRETA|COMMENTA]->(n:Norma)
                WHERE c.upvote_count > 0
                AND (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
                RETURN c.author_id as author_id, c.titolo as titolo, c.tipo as tipo,
                       c.upvote_count as upvote_count, c.downvote_count as downvote_count,
                       c.submission_date as submission_date, c.confidence as confidence,
                       c.expert_reviewed as expert_reviewed
                ORDER BY c.upvote_count DESC
                LIMIT 3
                """

                result = await session.run(query, concept=query_understanding.original_query or "")

                contributions = []
                async for record in result:
                    contributions.append(ContributionContext(
                        author_id=record["author_id"],
                        titolo=record["titolo"],
                        tipo=record["tipo"],
                        upvote_count=record.get("upvote_count", 0),
                        downvote_count=record.get("downvote_count", 0),
                        submission_date=record["submission_date"],
                        confidence=record.get("confidence", 0.60),
                        expert_reviewed=record.get("expert_reviewed", False)
                    ))

                return contributions

        except Exception as e:
            self.logger.error(f"Error querying contributions: {str(e)}", exc_info=True)
            return []

    async def _query_controversy_flags(self, query_understanding: QueryUnderstandingResult) -> List[ControversyFlag]:
        """Query controversial items flagged by RLCF."""
        try:
            async with self.neo4j_driver.session() as session:
                query = """
                MATCH (n:Norma)
                WHERE (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
                AND n.controversy_flag = true
                RETURN n.estremi as estremi, n.controversy_details as controversy_details
                """

                result = await session.run(query, concept=query_understanding.original_query or "")

                flags = []
                async for record in result:
                    details = record.get("controversy_details", {})
                    flags.append(ControversyFlag(
                        has_flag=True,
                        votes_conflicting=details.get("rlcf_votes", {}),
                        authority_avg=details.get("rlcf_authority_avg", 0.0),
                        last_flagged=details.get("last_flagged"),
                        notes=f"Norm {record['estremi']} has conflicting RLCF feedback"
                    ))

                return flags

        except Exception as e:
            self.logger.error(f"Error querying controversy flags: {str(e)}", exc_info=True)
            return []

    # ==========================================
    # Caching Methods
    # ==========================================

    def _generate_cache_key(self, query_understanding: QueryUnderstandingResult) -> str:
        """Generate cache key from query understanding result."""
        concept = (query_understanding.original_query or "").lower()
        key_data = f"{query_understanding.intent.value}:{concept}"
        key_hash = md5(key_data.encode()).hexdigest()[:12]
        return f"kg_enrich:{query_understanding.intent.value}:{key_hash}"

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get enriched context from Redis cache (if Redis available)."""
        if not self.redis_available:
            return None

        try:
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            self.logger.warning(f"Error getting from cache: {str(e)}")
            return None

    async def _cache_result(self, key: str, data: Dict[str, Any]) -> bool:
        """Cache enriched context in Redis for 24h (if Redis available)."""
        if not self.redis_available:
            return False

        try:
            ttl = self.config.cache.ttl_seconds if self.config else 86400  # 24h default

            # Custom serializer for Enum objects
            def enum_serializer(obj):
                if isinstance(obj, Enum):
                    return obj.value  # Return enum value instead of str(enum)
                return str(obj)

            await self.redis.setex(
                key,
                ttl,
                json.dumps(data, default=enum_serializer)
            )
            self.logger.debug(f"Cached {key} for {ttl}s")
            return True
        except Exception as e:
            self.logger.warning(f"Error caching result: {str(e)}")
            return False

    async def invalidate_cache(self, pattern: str = "kg_enrich:*") -> int:
        """Invalidate cache entries matching pattern (if Redis available)."""
        if not self.redis_available:
            self.logger.warning("Redis not available - cannot invalidate cache")
            return 0

        try:
            keys = await self.redis.keys(pattern)
            if keys:
                deleted = await self.redis.delete(*keys)
                self.logger.info(f"Invalidated {deleted} cache entries")
                return deleted
            return 0
        except Exception as e:
            self.logger.error(f"Error invalidating cache: {str(e)}")
            return 0

    # ==========================================
    # Utility Methods
    # ==========================================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics (if Redis available)."""
        if not self.redis_available:
            return {
                "redis_available": False,
                "used_memory": "N/A",
                "connected_clients": 0,
                "cache_enabled": False
            }

        try:
            info = await self.redis.info()
            return {
                "redis_available": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "cache_enabled": True,
                "total_commands_processed": info.get("total_commands_processed", 0),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0)
            }
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {str(e)}")
            return {}

    async def health_check(self) -> Dict[str, bool]:
        """Check service health (Neo4j + Redis)."""
        neo4j_ok = False
        redis_ok = False

        try:
            async with self.neo4j_driver.session() as session:
                await session.run("RETURN 1")
                neo4j_ok = True
        except Exception as e:
            self.logger.error(f"Neo4j health check failed: {str(e)}")

        try:
            await self.redis.ping()
            redis_ok = True
        except Exception as e:
            self.logger.error(f"Redis health check failed: {str(e)}")

        return {
            "neo4j": neo4j_ok,
            "redis": redis_ok,
            "healthy": neo4j_ok and redis_ok
        }


# ==========================================
# Factory Function
# ==========================================

async def create_kg_enrichment_service(
    neo4j_driver: AsyncDriver,
    redis_client: AsyncRedis,
    config: Optional[KGConfig] = None
) -> KGEnrichmentService:
    """
    Factory function to create KG enrichment service.

    Args:
        neo4j_driver: Neo4j async driver
        redis_client: Redis async client
        config: KG configuration (uses defaults if None)

    Returns:
        Initialized KGEnrichmentService instance
    """
    if config is None:
        config = KGConfig()

    service = KGEnrichmentService(neo4j_driver, redis_client, config)

    # Health check
    health = await service.health_check()
    if not health["healthy"]:
        logger.warning(
            f"KG service health check failed: Neo4j={health['neo4j']}, "
            f"Redis={health['redis']}"
        )

    return service
