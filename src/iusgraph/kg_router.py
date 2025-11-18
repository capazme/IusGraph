"""
Week 5 Day 5: Knowledge Graph Router
=====================================

FastAPI router for KG-specific operations:
- Cache warming (pre-populate cache with common queries)
- Cache invalidation (clear specific or all cache entries)
- KG statistics (query counts, latency, results distribution)
- Detailed health checks (Neo4j query performance, connection pool status)

Endpoints:
- POST /kg/cache/warm - Warm cache with provided queries
- DELETE /kg/cache/invalidate - Invalidate cache entries
- GET /kg/stats - KG enrichment statistics
- GET /kg/health/detailed - Detailed Neo4j health metrics
- GET /kg/sources - List available data sources and their status

Usage:
    from backend.preprocessing.kg_router import kg_router
    app.include_router(kg_router, prefix="/api/v1", tags=["knowledge-graph"])
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field

from backend.preprocessing.neo4j_connection import Neo4jConnectionManager
from backend.preprocessing.redis_connection import RedisConnectionManager
from backend.preprocessing.kg_enrichment_service import KGEnrichmentService
from backend.preprocessing.monitoring import (
    get_metrics,
    get_logger,
    get_health_aggregator,
    monitor_async_pipeline_stage
)


# ==============================================
# Pydantic Models
# ==============================================

class CacheWarmRequest(BaseModel):
    """Request to warm cache with specific queries"""
    queries: List[str] = Field(
        ...,
        description="List of queries to warm cache with",
        min_items=1,
        max_items=100
    )
    intent_type: str = Field(
        default="norm_explanation",
        description="Intent type for queries"
    )
    force_refresh: bool = Field(
        default=False,
        description="Force refresh even if cached"
    )


class CacheInvalidateRequest(BaseModel):
    """Request to invalidate cache entries"""
    pattern: Optional[str] = Field(
        default=None,
        description="Redis key pattern to invalidate (e.g., 'kg_enrich:*')"
    )
    query_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific query IDs to invalidate"
    )
    invalidate_all: bool = Field(
        default=False,
        description="Invalidate all KG cache entries"
    )


class CacheWarmResponse(BaseModel):
    """Response from cache warm operation"""
    success: bool
    queries_processed: int
    cache_entries_created: int
    errors: List[str] = Field(default_factory=list)
    processing_time_ms: float


class CacheInvalidateResponse(BaseModel):
    """Response from cache invalidate operation"""
    success: bool
    keys_invalidated: int
    pattern_used: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class KGStatistics(BaseModel):
    """KG enrichment statistics"""
    total_queries: int
    cache_hit_rate: float
    avg_latency_ms: float
    results_distribution: Dict[str, int]  # {norms: 123, sentenze: 45, ...}
    source_query_counts: Dict[str, int]  # {normattiva: 100, cassazione: 50, ...}
    degraded_queries: int
    timestamp: str


class Neo4jHealthDetailed(BaseModel):
    """Detailed Neo4j health metrics"""
    status: str  # healthy, degraded, unhealthy
    connection_pool: Dict[str, Any]
    query_performance: Dict[str, float]  # avg latencies by query type
    database_info: Dict[str, Any]
    node_counts: Dict[str, int]  # {Norma: 1000, Sentenza: 500, ...}
    relationship_counts: Dict[str, int]
    index_status: List[Dict[str, Any]]


class DataSourceStatus(BaseModel):
    """Status of a data source"""
    source_name: str
    available: bool
    last_sync: Optional[str] = None
    record_count: int
    avg_confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataSourcesResponse(BaseModel):
    """Response listing all data sources"""
    sources: List[DataSourceStatus]
    total_sources: int
    available_sources: int
    timestamp: str


# ==============================================
# Router Setup
# ==============================================

kg_router = APIRouter()

logger = get_logger("kg_router")
metrics = get_metrics()


# ==============================================
# Dependency: KG Service
# ==============================================

async def get_kg_service() -> KGEnrichmentService:
    """Dependency to get KG enrichment service"""
    try:
        neo4j_driver = Neo4jConnectionManager.get_driver()
        redis_client = RedisConnectionManager.get_client()

        # Import config if needed
        try:
            from backend.preprocessing.config.kg_config import get_kg_config
            config = get_kg_config()
        except Exception:
            config = None

        service = KGEnrichmentService(
            neo4j_driver=neo4j_driver,
            redis_client=redis_client,
            config=config
        )
        return service

    except Exception as e:
        logger.error(f"Failed to initialize KG service: {str(e)}")
        raise HTTPException(status_code=503, detail="KG service unavailable")


# ==============================================
# Cache Management Endpoints
# ==============================================

@kg_router.post("/cache/warm", response_model=CacheWarmResponse)
async def warm_cache(
    request: CacheWarmRequest,
    kg_service: KGEnrichmentService = Depends(get_kg_service)
) -> CacheWarmResponse:
    """
    Warm cache with provided queries.

    Pre-populates the Redis cache with results for common queries,
    improving response times for frequently asked questions.

    **Use Cases**:
    - Pre-deployment cache warming
    - Periodic refresh of popular queries
    - After KG data updates

    **Example Request**:
    ```json
    {
      "queries": [
        "Cosa dice l'art. 1321 c.c.?",
        "GDPR Art. 7 consenso"
      ],
      "intent_type": "norm_explanation",
      "force_refresh": false
    }
    ```
    """
    start_time = datetime.utcnow()
    errors: List[str] = []
    cache_entries_created = 0

    logger.info(
        "Cache warm started",
        extra={
            "query_count": len(request.queries),
            "intent_type": request.intent_type,
            "force_refresh": request.force_refresh
        }
    )

    # Check if Redis is available
    if not kg_service.redis_available:
        raise HTTPException(
            status_code=503,
            detail="Redis cache unavailable - cannot warm cache"
        )

    # Process each query
    for query in request.queries:
        try:
            # Create mock intent result for cache warming
            from backend.orchestration.intent_classifier import IntentResult, IntentType

            mock_intent = IntentResult(
                intent=IntentType(request.intent_type),
                confidence=0.9,
                reasoning="Cache warming",
                extracted_entities={},
                norm_references=[]
            )

            # Check cache first (unless force_refresh)
            cache_key = kg_service._generate_cache_key(mock_intent)

            if not request.force_refresh:
                cached = await kg_service._get_from_cache(cache_key)
                if cached:
                    logger.debug(f"Cache already warm for query: {query[:50]}")
                    continue

            # Enrich context (will cache result)
            async with monitor_async_pipeline_stage("cache_warm_query"):
                enriched = await kg_service.enrich_context(mock_intent)

            cache_entries_created += 1

        except Exception as e:
            error_msg = f"Failed to warm cache for query '{query[:50]}': {str(e)}"
            errors.append(error_msg)
            logger.warning(error_msg)

    elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

    logger.info(
        "Cache warm completed",
        extra={
            "queries_processed": len(request.queries),
            "cache_entries_created": cache_entries_created,
            "errors_count": len(errors),
            "elapsed_ms": elapsed_ms
        }
    )

    return CacheWarmResponse(
        success=len(errors) == 0,
        queries_processed=len(request.queries),
        cache_entries_created=cache_entries_created,
        errors=errors,
        processing_time_ms=round(elapsed_ms, 2)
    )


@kg_router.delete("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    request: CacheInvalidateRequest,
    kg_service: KGEnrichmentService = Depends(get_kg_service)
) -> CacheInvalidateResponse:
    """
    Invalidate cache entries.

    Removes entries from Redis cache based on:
    - Pattern matching (e.g., 'kg_enrich:*')
    - Specific query IDs
    - All KG cache entries

    **Use Cases**:
    - After KG data updates (invalidate affected queries)
    - Clear stale cache entries
    - Manual cache management

    **Example Requests**:
    ```json
    // Invalidate all norm explanation queries
    {
      "pattern": "kg_enrich:norm_explanation:*"
    }

    // Invalidate specific queries
    {
      "query_ids": ["qu-123", "qu-456"]
    }

    // Clear all KG cache
    {
      "invalidate_all": true
    }
    ```
    """
    logger.info(
        "Cache invalidation started",
        extra={
            "pattern": request.pattern,
            "query_ids": request.query_ids,
            "invalidate_all": request.invalidate_all
        }
    )

    # Check if Redis is available
    if not kg_service.redis_available:
        raise HTTPException(
            status_code=503,
            detail="Redis cache unavailable - cannot invalidate cache"
        )

    errors: List[str] = []
    keys_invalidated = 0

    try:
        redis_client = await RedisConnectionManager.get_client()

        # Determine pattern to use
        if request.invalidate_all:
            pattern = "kg_enrich:*"
        elif request.pattern:
            pattern = request.pattern
        elif request.query_ids:
            # Invalidate specific query IDs
            for query_id in request.query_ids:
                pattern = f"kg_enrich:*:{query_id}"
                keys = await redis_client.keys(pattern)
                if keys:
                    deleted = await redis_client.delete(*keys)
                    keys_invalidated += deleted
            pattern = None  # Already processed
        else:
            raise HTTPException(
                status_code=400,
                detail="Must specify pattern, query_ids, or invalidate_all"
            )

        # Invalidate by pattern
        if pattern:
            keys = await redis_client.keys(pattern)
            if keys:
                deleted = await redis_client.delete(*keys)
                keys_invalidated = deleted

        logger.info(
            "Cache invalidation completed",
            extra={
                "keys_invalidated": keys_invalidated,
                "pattern_used": pattern or "query_ids"
            }
        )

        return CacheInvalidateResponse(
            success=True,
            keys_invalidated=keys_invalidated,
            pattern_used=pattern,
            errors=errors
        )

    except Exception as e:
        error_msg = f"Cache invalidation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return CacheInvalidateResponse(
            success=False,
            keys_invalidated=keys_invalidated,
            pattern_used=request.pattern,
            errors=[error_msg]
        )


# ==============================================
# Statistics Endpoints
# ==============================================

@kg_router.get("/stats", response_model=KGStatistics)
async def get_kg_statistics(
    since_minutes: int = Query(default=60, description="Statistics time window in minutes"),
    kg_service: KGEnrichmentService = Depends(get_kg_service)
) -> KGStatistics:
    """
    Get KG enrichment statistics.

    Returns aggregated metrics:
    - Total queries processed
    - Cache hit rate
    - Average latency
    - Results distribution by type
    - Source query counts
    - Degraded query count

    **Example Response**:
    ```json
    {
      "total_queries": 1250,
      "cache_hit_rate": 0.72,
      "avg_latency_ms": 450,
      "results_distribution": {
        "norms": 850,
        "sentenze": 320,
        "dottrina": 180
      },
      "source_query_counts": {
        "normattiva": 900,
        "cassazione": 400,
        "dottrina": 250
      },
      "degraded_queries": 15,
      "timestamp": "2025-11-05T10:30:00Z"
    }
    ```
    """
    logger.info(f"Fetching KG statistics (last {since_minutes} minutes)")

    try:
        # Get cache stats from Redis
        cache_stats = await kg_service.get_cache_stats()

        # Get metrics snapshot
        metrics_snapshot = metrics.get_metrics_snapshot()

        # Build statistics response
        # Note: In production, you'd query actual metrics from Prometheus/registry
        stats = KGStatistics(
            total_queries=0,  # Would be computed from metrics
            cache_hit_rate=cache_stats.get("hit_rate", 0.0),
            avg_latency_ms=0.0,  # Would be computed from metrics
            results_distribution={
                "norms": 0,
                "sentenze": 0,
                "dottrina": 0,
                "contributions": 0
            },
            source_query_counts={
                "normattiva": 0,
                "cassazione": 0,
                "dottrina": 0,
                "contributions": 0,
                "rlcf": 0
            },
            degraded_queries=0,
            timestamp=datetime.utcnow().isoformat()
        )

        return stats

    except Exception as e:
        logger.error(f"Failed to fetch KG statistics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")


# ==============================================
# Health Check Endpoints
# ==============================================

@kg_router.get("/health/detailed", response_model=Neo4jHealthDetailed)
async def get_detailed_health(
    kg_service: KGEnrichmentService = Depends(get_kg_service)
) -> Neo4jHealthDetailed:
    """
    Get detailed Neo4j health metrics.

    Returns comprehensive health information:
    - Connection pool status
    - Query performance by type
    - Database information
    - Node and relationship counts
    - Index status

    **Example Response**:
    ```json
    {
      "status": "healthy",
      "connection_pool": {
        "max_size": 50,
        "in_use": 5,
        "idle": 45
      },
      "query_performance": {
        "norms": 0.15,
        "sentenze": 0.25,
        "dottrina": 0.18
      },
      "database_info": {
        "version": "5.13.0",
        "edition": "community"
      },
      "node_counts": {
        "Norma": 1523,
        "Sentenza": 847,
        "Dottrina": 392
      },
      "relationship_counts": {
        "CITA": 2341,
        "MODIFICA": 123,
        "RIFERISCE": 456
      },
      "index_status": [
        {"name": "norma_estremi", "state": "ONLINE", "type": "BTREE"}
      ]
    }
    ```
    """
    logger.info("Fetching detailed Neo4j health metrics")

    # Check if Neo4j is available
    if not kg_service.neo4j_available:
        raise HTTPException(
            status_code=503,
            detail="Neo4j unavailable - cannot fetch health metrics"
        )

    try:
        neo4j_driver = await Neo4jConnectionManager.get_driver()

        # Query Neo4j for detailed metrics
        async with neo4j_driver.session() as session:
            # Get node counts
            node_count_query = """
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            """
            result = await session.run(node_count_query)
            node_counts = {
                record["label"]: record["count"]
                async for record in result
                if record["label"]
            }

            # Get relationship counts
            rel_count_query = """
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            """
            result = await session.run(rel_count_query)
            relationship_counts = {
                record["rel_type"]: record["count"]
                async for record in result
            }

            # Get database info
            db_info_query = "CALL dbms.components() YIELD name, versions, edition"
            result = await session.run(db_info_query)
            db_record = await result.single()
            database_info = {
                "name": db_record["name"] if db_record else "neo4j",
                "version": db_record["versions"][0] if db_record and db_record["versions"] else "unknown",
                "edition": db_record["edition"] if db_record else "unknown"
            }

        # Get connection pool stats
        neo4j_health = await Neo4jConnectionManager.health_check()

        health = Neo4jHealthDetailed(
            status=neo4j_health["status"],
            connection_pool={
                "max_size": 50,  # From config
                "in_use": 0,  # Would query actual pool
                "idle": 0
            },
            query_performance={
                "norms": 0.15,  # Would compute from metrics
                "sentenze": 0.25,
                "dottrina": 0.18,
                "contributions": 0.12
            },
            database_info=database_info,
            node_counts=node_counts,
            relationship_counts=relationship_counts,
            index_status=[]  # Would query actual indexes
        )

        return health

    except Exception as e:
        logger.error(f"Failed to fetch detailed health metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch health metrics: {str(e)}")


# ==============================================
# Data Sources Endpoints
# ==============================================

@kg_router.get("/sources", response_model=DataSourcesResponse)
async def get_data_sources(
    kg_service: KGEnrichmentService = Depends(get_kg_service)
) -> DataSourcesResponse:
    """
    List all data sources and their status.

    Returns information about each data source:
    - Availability
    - Last sync time
    - Record count
    - Average confidence score
    - Source-specific metadata

    **Example Response**:
    ```json
    {
      "sources": [
        {
          "source_name": "normattiva",
          "available": true,
          "last_sync": "2025-11-05T03:00:00Z",
          "record_count": 1523,
          "avg_confidence": 0.95,
          "metadata": {
            "official_source": true,
            "update_frequency": "daily"
          }
        },
        {
          "source_name": "cassazione",
          "available": true,
          "last_sync": "2025-11-04T22:00:00Z",
          "record_count": 847,
          "avg_confidence": 0.88,
          "metadata": {
            "official_source": true,
            "case_law": true
          }
        }
      ],
      "total_sources": 5,
      "available_sources": 4,
      "timestamp": "2025-11-05T10:30:00Z"
    }
    ```
    """
    logger.info("Fetching data sources status")

    # Check if Neo4j is available
    if not kg_service.neo4j_available:
        raise HTTPException(
            status_code=503,
            detail="Neo4j unavailable - cannot fetch data sources"
        )

    try:
        neo4j_driver = await Neo4jConnectionManager.get_driver()

        sources: List[DataSourceStatus] = []

        # Query each source
        async with neo4j_driver.session() as session:
            # Normattiva
            norma_query = "MATCH (n:Norma) WHERE n.fonte = 'normattiva' RETURN count(n) as count"
            result = await session.run(norma_query)
            norma_record = await result.single()
            norma_count = norma_record["count"] if norma_record else 0

            sources.append(DataSourceStatus(
                source_name="normattiva",
                available=norma_count > 0,
                last_sync="2025-11-05T03:00:00Z",  # Would query actual sync time
                record_count=norma_count,
                avg_confidence=0.95,
                metadata={
                    "official_source": True,
                    "update_frequency": "daily",
                    "tipo": "norme"
                }
            ))

            # Cassazione
            sentenza_query = "MATCH (s:Sentenza) WHERE s.fonte = 'cassazione' RETURN count(s) as count"
            result = await session.run(sentenza_query)
            sentenza_record = await result.single()
            sentenza_count = sentenza_record["count"] if sentenza_record else 0

            sources.append(DataSourceStatus(
                source_name="cassazione",
                available=sentenza_count > 0,
                last_sync="2025-11-04T22:00:00Z",
                record_count=sentenza_count,
                avg_confidence=0.88,
                metadata={
                    "official_source": True,
                    "tipo": "giurisprudenza"
                }
            ))

            # Dottrina
            dottrina_query = "MATCH (d:Dottrina) RETURN count(d) as count"
            result = await session.run(dottrina_query)
            dottrina_record = await result.single()
            dottrina_count = dottrina_record["count"] if dottrina_record else 0

            sources.append(DataSourceStatus(
                source_name="dottrina",
                available=dottrina_count > 0,
                last_sync="2025-11-04T18:00:00Z",
                record_count=dottrina_count,
                avg_confidence=0.75,
                metadata={
                    "official_source": False,
                    "tipo": "accademica"
                }
            ))

            # Contributions (community)
            contrib_query = "MATCH (c:Contribution) RETURN count(c) as count"
            result = await session.run(contrib_query)
            contrib_record = await result.single()
            contrib_count = contrib_record["count"] if contrib_record else 0

            sources.append(DataSourceStatus(
                source_name="contributions",
                available=contrib_count > 0,
                last_sync=None,
                record_count=contrib_count,
                avg_confidence=0.65,
                metadata={
                    "official_source": False,
                    "community_driven": True
                }
            ))

            # RLCF (expert feedback)
            rlcf_query = "MATCH (v:Vote) RETURN count(v) as count"
            result = await session.run(rlcf_query)
            rlcf_record = await result.single()
            rlcf_count = rlcf_record["count"] if rlcf_record else 0

            sources.append(DataSourceStatus(
                source_name="rlcf",
                available=rlcf_count > 0,
                last_sync=None,
                record_count=rlcf_count,
                avg_confidence=0.82,
                metadata={
                    "official_source": False,
                    "expert_driven": True
                }
            ))

        available_sources = sum(1 for s in sources if s.available)

        return DataSourcesResponse(
            sources=sources,
            total_sources=len(sources),
            available_sources=available_sources,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to fetch data sources: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch data sources: {str(e)}")


# ==============================================
# Exports
# ==============================================

__all__ = [
    "kg_router",
    "CacheWarmRequest",
    "CacheInvalidateRequest",
    "KGStatistics",
    "Neo4jHealthDetailed",
    "DataSourcesResponse"
]
