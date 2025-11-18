"""
Knowledge Graph Configuration

Pydantic models for loading and validating kg_config.yaml configuration file.
Supports environment variable expansion and sensible defaults.
"""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ===========================================
# Connection Configuration Models
# ===========================================

class Neo4jConfig(BaseModel):
    """Neo4j database configuration"""
    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: str
    database: str = Field(default="neo4j")
    max_connection_pool_size: int = Field(default=50)
    connection_acquisition_timeout: int = Field(default=60)
    connection_timeout: int = Field(default=30)
    max_transaction_retry_time: int = Field(default=30)
    fetch_size: int = Field(default=1000)
    default_access_mode: Literal["READ", "WRITE"] = Field(default="READ")


class RedisConfig(BaseModel):
    """Redis cache configuration"""
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = None
    max_connections: int = Field(default=10)
    socket_timeout: int = Field(default=5)
    socket_connect_timeout: int = Field(default=5)
    socket_keepalive: bool = Field(default=True)
    default_ttl: int = Field(default=86400)  # 24 hours
    key_prefix: str = Field(default="merl-t:kg:")
    cache_ttl: Dict[str, int] = Field(default_factory=lambda: {
        "norma": 604800,  # 7 days
        "sentenza": 86400,  # 1 day
        "dottrina": 172800,  # 2 days
        "contributo": 3600,  # 1 hour
        "rlcf": 1800  # 30 minutes
    })


# ===========================================
# Enrichment Configuration Models
# ===========================================

class QuorumConfig(BaseModel):
    """Quorum requirements for entity types"""
    min_experts: Optional[int] = None
    min_authority: Optional[float] = None
    min_votes: Optional[int] = None
    min_net_positive: Optional[int] = None


class ControversyConfig(BaseModel):
    """Controversy detection configuration"""
    entropy_threshold: float = Field(default=0.7)
    polarization_threshold: float = Field(default=0.6)


class EnrichmentConfig(BaseModel):
    """KG enrichment service configuration"""
    max_parallel_queries: int = Field(default=5)
    query_timeout: int = Field(default=10)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    max_results: Dict[str, int] = Field(default_factory=lambda: {
        "norms": 20,
        "sentenze": 15,
        "dottrina": 10,
        "related_norms": 10,
        "concepts": 30
    })
    source_weights: Dict[str, float] = Field(default_factory=lambda: {
        "normattiva": 1.0,
        "cassazione": 0.95,
        "dottrina": 0.85,
        "community": 0.70,
        "rlcf": 0.90
    })
    quorum: Dict[str, QuorumConfig] = Field(default_factory=dict)
    controversy: ControversyConfig = Field(default_factory=ControversyConfig)

    @validator('quorum', pre=True)
    def convert_quorum(cls, v):
        """Convert dict of dicts to dict of QuorumConfig"""
        if isinstance(v, dict):
            return {k: QuorumConfig(**val) if isinstance(val, dict) else val
                    for k, val in v.items()}
        return v


# ===========================================
# Data Sources Configuration Models
# ===========================================

class DataSourceConfig(BaseModel):
    """Generic data source configuration"""
    enabled: bool = Field(default=True)
    api_url: Optional[str] = None
    timeout: int = Field(default=30)
    retry_attempts: int = Field(default=3)
    cache_ttl: int = Field(default=86400)


class DottrinaSourceConfig(BaseModel):
    """Dottrina-specific source configuration"""
    enabled: bool = Field(default=True)
    sources: List[str] = Field(default_factory=list)
    cache_ttl: int = Field(default=172800)


class CommunitySourceConfig(BaseModel):
    """Community contributions source configuration"""
    enabled: bool = Field(default=True)
    voting_window_days: int = Field(default=7)
    auto_approval_threshold: int = Field(default=10)
    require_expert_review: bool = Field(default=True)
    cache_ttl: int = Field(default=3600)


class RLCFSourceConfig(BaseModel):
    """RLCF consensus source configuration"""
    enabled: bool = Field(default=True)
    min_quorum: int = Field(default=3)
    min_authority: float = Field(default=0.75)
    cache_ttl: int = Field(default=1800)


class DataSourcesConfig(BaseModel):
    """All data sources configuration"""
    normattiva: DataSourceConfig = Field(default_factory=DataSourceConfig)
    cassazione: DataSourceConfig = Field(default_factory=DataSourceConfig)
    dottrina: DottrinaSourceConfig = Field(default_factory=DottrinaSourceConfig)
    community: CommunitySourceConfig = Field(default_factory=CommunitySourceConfig)
    rlcf: RLCFSourceConfig = Field(default_factory=RLCFSourceConfig)


# ===========================================
# Query Configuration Models
# ===========================================

class QueriesConfig(BaseModel):
    """Cypher query configuration"""
    complex_query_timeout: int = Field(default=30)
    max_relationship_depth: Dict[str, int] = Field(default_factory=lambda: {
        "modifica": 3,
        "abrogato_da": 3,
        "tratta": 2,
        "applica": 2
    })
    batch_sizes: Dict[str, int] = Field(default_factory=lambda: {
        "import": 1000,
        "update": 500,
        "delete": 100
    })


# ===========================================
# Performance Configuration Models
# ===========================================

class PerformanceConfig(BaseModel):
    """Performance and optimization configuration"""
    enable_query_cache: bool = Field(default=True)
    query_cache_size: int = Field(default=1000)
    connection_lifetime: int = Field(default=3600)
    max_retries: int = Field(default=3)
    retry_delay: int = Field(default=1)
    log_queries: bool = Field(default=True)
    log_slow_queries: bool = Field(default=True)
    slow_query_threshold: float = Field(default=1.0)
    collect_metrics: bool = Field(default=True)
    metrics_interval: int = Field(default=60)


# ===========================================
# Versioning Configuration Models
# ===========================================

class VersionStrategyConfig(BaseModel):
    """Versioning strategy for an entity type"""
    type: Literal["full_chain", "current_plus_archive", "latest_only"]
    archive_after_days: Optional[int] = None


class VersioningConfig(BaseModel):
    """Temporal versioning configuration"""
    strategies: Dict[str, VersionStrategyConfig] = Field(default_factory=dict)
    enable_auto_archive: bool = Field(default=True)
    archive_location: str = Field(default="archived")

    @validator('strategies', pre=True)
    def convert_strategies(cls, v):
        """Convert dict of dicts to dict of VersionStrategyConfig"""
        if isinstance(v, dict):
            return {k: VersionStrategyConfig(**val) if isinstance(val, dict) else val
                    for k, val in v.items()}
        return v


# ===========================================
# Error Handling Configuration Models
# ===========================================

class ErrorHandlingConfig(BaseModel):
    """Error handling configuration"""
    retry_on_connection_error: bool = Field(default=True)
    retry_on_timeout: bool = Field(default=True)
    retry_on_transient_error: bool = Field(default=True)
    fallback_to_cache: bool = Field(default=True)
    fallback_to_partial_results: bool = Field(default=True)
    report_errors: bool = Field(default=True)
    error_log_file: str = Field(default="logs/kg_errors.log")


# ===========================================
# Development Configuration Models
# ===========================================

class DevelopmentConfig(BaseModel):
    """Development and testing configuration"""
    debug: bool = Field(default=False)
    use_mock_driver: bool = Field(default=False)
    use_sample_data: bool = Field(default=False)
    sample_data_file: str = Field(default="tests/fixtures/sample_kg_data.json")
    disable_cache: bool = Field(default=False)


# ===========================================
# Feature Flags Configuration Models
# ===========================================

class FeaturesConfig(BaseModel):
    """Feature flags configuration"""
    multi_source_enrichment: bool = Field(default=True)
    rlcf_integration: bool = Field(default=True)
    controversy_detection: bool = Field(default=True)
    community_contributions: bool = Field(default=True)
    ner_feedback_loop: bool = Field(default=True)
    temporal_queries: bool = Field(default=True)
    provenance_tracking: bool = Field(default=True)


# ===========================================
# Monitoring Configuration Models
# ===========================================

class MonitoringAlertsConfig(BaseModel):
    """Monitoring alert thresholds"""
    high_error_rate: float = Field(default=0.05)
    slow_query_rate: float = Field(default=0.10)
    cache_miss_rate: float = Field(default=0.50)
    connection_pool_exhaustion: float = Field(default=0.90)


class MonitoringConfig(BaseModel):
    """Monitoring and alerting configuration"""
    enabled: bool = Field(default=True)
    metrics: List[str] = Field(default_factory=lambda: [
        "query_latency",
        "cache_hit_rate",
        "error_rate",
        "connection_pool_usage",
        "query_throughput"
    ])
    alerts: MonitoringAlertsConfig = Field(default_factory=MonitoringAlertsConfig)
    report_interval: int = Field(default=300)
    report_destination: str = Field(default="logs/kg_metrics.log")


# ===========================================
# Document Ingestion Configuration Models
# ===========================================

class LLMConfig(BaseModel):
    """LLM configuration for document ingestion"""
    provider: str = Field(default="openrouter")
    model: str = Field(default="google/gemini-2.5-flash")
    api_key: str
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=4000)
    timeout_seconds: int = Field(default=60)


class DocumentReaderConfig(BaseModel):
    """Document reader configuration"""
    supported_formats: List[str] = Field(default_factory=lambda: ["pdf", "docx", "txt", "md"])
    max_file_size_mb: int = Field(default=50)
    ocr_enabled: bool = Field(default=False)
    paragraph_min_words: int = Field(default=10)
    context_chars: int = Field(default=100)


class ExtractionConfig(BaseModel):
    """Extraction settings for document ingestion"""
    batch_size: int = Field(default=10)
    parallel_requests: int = Field(default=3)
    confidence_threshold: float = Field(default=0.7)
    retry_attempts: int = Field(default=3)
    cache_enabled: bool = Field(default=True)
    cache_ttl_hours: int = Field(default=24)


class ValidationConfig(BaseModel):
    """Validation settings for document ingestion"""
    strict_mode: bool = Field(default=False)
    enrich_with_external: bool = Field(default=True)
    resolve_references: bool = Field(default=True)
    min_confidence: float = Field(default=0.7)


class WritingConfig(BaseModel):
    """Neo4j writing settings for document ingestion"""
    batch_size: int = Field(default=100)
    auto_approve: bool = Field(default=False)
    duplicate_strategy: Literal["merge", "skip", "error"] = Field(default="merge")
    provenance_required: bool = Field(default=True)


class CostControlConfig(BaseModel):
    """Cost control for LLM API usage"""
    max_cost_per_document_usd: float = Field(default=5.0)
    alert_threshold_usd: float = Field(default=100.0)
    track_costs: bool = Field(default=True)


class IngestionMonitoringConfig(BaseModel):
    """Monitoring for document ingestion"""
    log_level: str = Field(default="INFO")
    track_performance: bool = Field(default=True)
    export_stats: bool = Field(default=True)
    stats_file: str = Field(default="ingestion_stats.json")


class DocumentIngestionConfig(BaseModel):
    """Complete document ingestion configuration"""
    llm: LLMConfig
    reader: DocumentReaderConfig = Field(default_factory=DocumentReaderConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    writing: WritingConfig = Field(default_factory=WritingConfig)
    cost_control: CostControlConfig = Field(default_factory=CostControlConfig)
    monitoring: IngestionMonitoringConfig = Field(default_factory=IngestionMonitoringConfig)


# ===========================================
# Main Configuration Model
# ===========================================

class KGConfig(BaseModel):
    """Complete Knowledge Graph configuration"""
    neo4j: Neo4jConfig
    redis: RedisConfig = Field(default_factory=RedisConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    queries: QueriesConfig = Field(default_factory=QueriesConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    versioning: VersioningConfig = Field(default_factory=VersioningConfig)
    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    document_ingestion: Optional[DocumentIngestionConfig] = None


# ===========================================
# Configuration Loading Function
# ===========================================

def _expand_env_vars(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively expand environment variables in configuration dictionary.

    Supports ${VAR} and ${VAR:-default} syntax.

    Args:
        config_dict: Configuration dictionary

    Returns:
        Dictionary with environment variables expanded
    """
    env_var_pattern = re.compile(r'\$\{([^}^{]+)\}')

    def expand_value(value):
        if isinstance(value, str):
            def replace_var(match):
                var_expr = match.group(1)

                # Check for default value syntax: ${VAR:-default}
                if ':-' in var_expr:
                    var_name, default_val = var_expr.split(':-', 1)
                    return os.getenv(var_name.strip(), default_val.strip())
                else:
                    # No default, just get environment variable
                    var_name = var_expr.strip()
                    env_value = os.getenv(var_name)

                    if env_value is None:
                        logger.warning(f"Environment variable '{var_name}' not set, using original value")
                        return match.group(0)  # Return original ${VAR}

                    return env_value

            return env_var_pattern.sub(replace_var, value)

        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [expand_value(item) for item in value]

        else:
            return value

    return expand_value(config_dict)


def load_kg_config(config_path: Optional[str] = None) -> KGConfig:
    """
    Load Knowledge Graph configuration from YAML file.

    Args:
        config_path: Path to kg_config.yaml file. If None, looks in standard location.

    Returns:
        KGConfig instance with validated configuration

    Raises:
        FileNotFoundError: If configuration file not found
        ValueError: If configuration is invalid
    """
    # Determine config file path
    if config_path is None:
        # Look in standard location relative to this file
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / "kg_config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading KG configuration from: {config_path}")

    # Load YAML file
    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    # Expand environment variables
    config_dict = _expand_env_vars(config_dict)

    # Validate and create Pydantic model
    try:
        config = KGConfig(**config_dict)
        logger.info("KG configuration loaded and validated successfully")
        return config

    except Exception as e:
        logger.error(f"Failed to load KG configuration: {str(e)}", exc_info=True)
        raise ValueError(f"Invalid KG configuration: {str(e)}")


# Singleton instance
_kg_config_instance: Optional[KGConfig] = None


def get_kg_config(reload: bool = False) -> KGConfig:
    """
    Get singleton KGConfig instance.

    Args:
        reload: Force reload from file

    Returns:
        KGConfig instance
    """
    global _kg_config_instance

    if _kg_config_instance is None or reload:
        _kg_config_instance = load_kg_config()

    return _kg_config_instance
