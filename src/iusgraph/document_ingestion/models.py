"""
Data Models for Document Ingestion
====================================

Defines all data structures used in the ingestion pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum


# =================================================================
# ENUMS
# =================================================================

class DocumentFormat(Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "md"


class ExtractionMethod(Enum):
    """Method used to extract text."""
    PYPDF2 = "pypdf2"
    PDFPLUMBER = "pdfplumber"
    PYTHON_DOCX = "python_docx"
    PLAIN_TEXT = "plain_text"
    OCR = "ocr"


class NodeType(Enum):
    """Knowledge Graph node types (from knowledge-graph.md)."""
    # Primary types (A-W)
    NORMA = "Norma"
    CONCETTO_GIURIDICO = "Concetto Giuridico"
    SOGGETTO_GIURIDICO = "Soggetto Giuridico"
    ATTO_GIUDIZIARIO = "Atto Giudiziario"
    DOTTRINA = "Dottrina"
    PROCEDURA = "Procedura"
    COMMA_LETTERA_NUMERO = "Comma/Lettera/Numero"
    VERSIONE = "Versione"
    DIRETTIVA_UE = "Direttiva UE"
    REGOLAMENTO_UE = "Regolamento UE"
    ORGANO_GIURISDIZIONALE = "Organo Giurisdizionale"
    CASO_FATTO = "Caso/Fatto"
    TERMINE_SCADENZA = "Termine/Scadenza"
    SANZIONE = "Sanzione"
    DEFINIZIONE_LEGALE = "Definizione Legale"
    MODALITA_GIURIDICA = "Modalità Giuridica"
    RESPONSABILITA = "Responsabilità"
    DIRITTO_SOGGETTIVO = "Diritto Soggettivo"
    INTERESSE_LEGITTIMO = "Interesse Legittimo"
    PRINCIPIO_GIURIDICO = "Principio Giuridico"
    FATTO_GIURIDICO = "Fatto Giuridico"
    RUOLO_GIURIDICO = "Ruolo Giuridico"
    REGOLA = "Regola"
    PROPOSIZIONE_GIURIDICA = "Proposizione Giuridica"


class RelationType(Enum):
    """Knowledge Graph relationship types (from knowledge-graph.md)."""
    # 3.2 Structural Relations
    CONTIENE = "contiene"
    PARTE_DI = "parte_di"
    VERSIONE_PRECEDENTE = "versione_precedente"
    VERSIONE_SUCCESSIVA = "versione_successiva"
    HA_VERSIONE = "ha_versione"

    # 3.3 Modification Relations
    SOSTITUISCE = "sostituisce"
    INSERISCE = "inserisce"
    ABROGA_TOTALMENTE = "abroga_totalmente"
    ABROGA_PARZIALMENTE = "abroga_parzialmente"
    SOSPENDE = "sospende"
    PROROGA = "proroga"
    INTEGRA = "integra"
    DEROGA_A = "deroga_a"
    CONSOLIDA = "consolida"

    # 3.4 Semantic Relations
    DISCIPLINA = "disciplina"
    APPLICA_A = "applica_a"
    DEFINISCE = "definisce"
    PREVEDE_SANZIONE = "prevede_sanzione"
    STABILISCE_TERMINE = "stabilisce_termine"
    PREVEDE = "prevede"

    # 3.5 Dependency Relations
    DIPENDE_DA = "dipende_da"
    PRESUPPONE = "presuppone"
    SPECIES = "species"

    # 3.6 Citation and Interpretation Relations
    CITA = "cita"
    INTERPRETA = "interpreta"
    COMMENTA = "commenta"
    DISCUTE = "discute"

    # 3.7 European and International Relations
    ATTUA = "attua"
    RECEPISCE = "recepisce"
    CONFORME_A = "conforme_a"

    # 3.8 Institutional Relations
    EMESSO_DA = "emesso_da"
    HA_COMPETENZA_SU = "ha_competenza_su"
    GERARCHICAMENTE_SUPERIORE = "gerarchicamente_superiore"

    # 3.9 Case-based Relations
    RIGUARDA = "riguarda"
    APPLICA_NORMA_A_CASO = "applica_norma_a_caso"
    PRECEDENTE_DI = "precedente_di"

    # 3.10 Classification and Organization
    FONTE = "fonte"
    CLASSIFICA_IN = "classifica_in"

    # 3.11 LKIF-Aligned Relations
    IMPONE = "impone"
    CONFERISCE = "conferisce"
    TITOLARE_DI = "titolare_di"
    RIVESTE_RUOLO = "riveste_ruolo"
    ATTRIBUISCE_RESPONSABILITA = "attribuisce_responsabilita"
    RESPONSABILE_PER = "responsabile_per"
    ESPRIME_PRINCIPIO = "esprime_principio"
    CONFORMA_A_PRINCIPIO = "conforma_a" # Renamed to avoid conflict with 29
    DEROGA_PRINCIPIO = "deroga_principio"
    BILANCIA_CON = "bilancia_con"
    PRODUCE_EFFETTO = "produce_effetto"
    PRESUPPOSTO_DI = "presupposto_di"
    COSTITUTIVO_DI = "costitutivo_di"
    ESTINGUE = "estingue"
    MODIFICA_EFFICACIA = "modifica_efficacia"
    APPLICA_REGOLA = "applica_regola"
    IMPLICA = "implica"
    CONTRADDICE = "contradice"
    GIUSTIFICA = "giustifica"
    LIMITA = "limita"
    TUTELA = "tutela"
    VIOLA = "viola"
    COMPATIBILE_CON = "compatibile_con"
    INCOMPATIBILE_CON = "incompatibile_con"
    SPECIFICA = "specifica"
    ESEMPLIFICA = "esemplifica"
    CAUSA_DI = "causa_di"
    CONDIZIONE_DI = "condizione_di"



# =================================================================
# PROVENANCE
# =================================================================

@dataclass
class Provenance:
    """
    Tracks the origin of extracted information.

    Ensures every piece of knowledge can be traced back to its source.
    """
    source_file: str
    """Full path to source document"""

    page_number: Optional[int] = None
    """Page number in document (None for non-paginated formats)"""

    paragraph_index: int = 0
    """Sequential paragraph index within page/document"""

    char_start: int = 0
    """Character offset where text starts"""

    char_end: int = 0
    """Character offset where text ends"""

    extraction_method: ExtractionMethod = ExtractionMethod.PLAIN_TEXT
    """Method used to extract the text"""

    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    """When the extraction occurred"""

    context_before: str = ""
    """Text before the extracted segment (for verification)"""

    context_after: str = ""
    """Text after the extracted segment (for verification)"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "source_file": self.source_file,
            "page_number": self.page_number,
            "paragraph_index": self.paragraph_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "extraction_method": self.extraction_method.value,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "context_before": self.context_before[:100],  # Limit size
            "context_after": self.context_after[:100],
        }


# =================================================================
# DOCUMENT SEGMENT
# =================================================================

@dataclass
class DocumentSegment:
    """
    Represents a segment of text from a document.

    Segments are typically paragraphs or logical text blocks.
    """
    text: str
    """The actual text content"""

    provenance: Provenance
    """Where this text came from"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata (e.g., structure type, formatting)"""

    segment_id: str = ""
    """Unique identifier for this segment"""

    def __post_init__(self):
        """Generate segment ID if not provided."""
        if not self.segment_id:
            # Format: filename:page:para
            filename = Path(self.provenance.source_file).stem
            page = self.provenance.page_number or 0
            para = self.provenance.paragraph_index
            self.segment_id = f"{filename}:p{page}:para{para}"


# =================================================================
# EXTRACTED ENTITIES & RELATIONSHIPS
# =================================================================

@dataclass
class ExtractedEntity:
    """
    An entity extracted from text by LLM.

    Maps to one of the 23 KG node types.
    """
    type: NodeType
    """Type of entity (one of 23 KG node types)"""

    label: str
    """Human-readable label (e.g., "Art. 1321 c.c.", "Principio di Legalità")"""

    properties: Dict[str, Any]
    """All properties per KG schema for this node type"""

    confidence: float
    """LLM confidence score (0.0 - 1.0)"""

    provenance: Provenance
    """Where this entity was extracted from"""

    entity_id: str = ""
    """Unique identifier (auto-generated if not provided)"""

    def __post_init__(self):
        """Generate entity ID if not provided."""
        if not self.entity_id:
            # Use label as basis for ID (sanitized)
            import re
            sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', self.label.lower())
            self.entity_id = f"{self.type.value.lower().replace(' ', '_')}_{sanitized}"


@dataclass
class ExtractedRelationship:
    """
    A relationship between two entities extracted by LLM.
    """
    source_label: str
    """Label of source entity"""

    target_label: str
    """Label of target entity"""

    type: RelationType
    """Type of relationship"""

    properties: Dict[str, Any] = field(default_factory=dict)
    """Additional properties for the relationship"""

    confidence: float = 1.0
    """LLM confidence score (0.0 - 1.0)"""

    provenance: Provenance = None
    """Where this relationship was inferred from"""

    bidirectional: bool = False
    """If true, create relationship in both directions"""


# =================================================================
# EXTRACTION RESULT
# =================================================================

@dataclass
class ExtractionResult:
    """
    Result of LLM extraction for a single document segment.
    """
    segment: DocumentSegment
    """The segment that was processed"""

    entities: List[ExtractedEntity] = field(default_factory=list)
    """Entities extracted from this segment"""

    relationships: List[ExtractedRelationship] = field(default_factory=list)
    """Relationships extracted from this segment"""

    llm_model: str = ""
    """LLM model used (e.g., "google/gemini-2.5-flash")"""

    cost_usd: float = 0.0
    """Cost in USD for this extraction"""

    duration_seconds: float = 0.0
    """Time taken for extraction"""

    tokens_input: int = 0
    """Number of input tokens"""

    tokens_output: int = 0
    """Number of output tokens"""

    error: Optional[str] = None
    """Error message if extraction failed"""

    raw_response: str = ""
    prompt: str = ""
    """Raw LLM response (for debugging)"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "segment_id": self.segment.segment_id,
            "llm_model": self.llm_model,
            "cost_usd": round(self.cost_usd, 6),
            "duration_seconds": round(self.duration_seconds, 2),
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "error": self.error,
            "entities_extracted": [e.label for e in self.entities],
            "relationships_extracted": [f"{r.source_label} -[{r.type.value}]-> {r.target_label}" for r in self.relationships],
            "raw_response": self.raw_response,
            "prompt": self.prompt,
        }


# =================================================================
# INGESTION RESULT
# =================================================================

@dataclass
class IngestionResult:
    """
    Result of ingesting a complete document.
    """
    file_path: Path
    """Path to ingested document"""

    segments_processed: int = 0
    """Number of segments processed"""

    entities_extracted: int = 0
    """Number of entities extracted"""

    entities_written: int = 0
    """Number of entities written to Neo4j"""

    relationships_created: int = 0
    """Number of relationships created"""

    duration_seconds: float = 0.0
    """Total time for ingestion"""

    cost_usd: float = 0.0
    """Total LLM cost"""

    errors: List[str] = field(default_factory=list)
    """List of errors encountered"""

    warnings: List[str] = field(default_factory=list)
    """List of warnings"""

    dry_run: bool = False
    """If true, no data was written to Neo4j"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "file_path": str(self.file_path),
            "segments_processed": self.segments_processed,
            "entities_extracted": self.entities_extracted,
            "entities_written": self.entities_written,
            "relationships_created": self.relationships_created,
            "duration_seconds": round(self.duration_seconds, 2),
            "cost_usd": round(self.cost_usd, 4),
            "errors": self.errors,
            "warnings": self.warnings,
            "dry_run": self.dry_run,
            "metadata": self.metadata,
        }

    def print_summary(self):
        """Print human-readable summary."""
        print("=" * 60)
        print(f"INGESTION RESULT: {self.file_path.name}")
        print("=" * 60)
        print(f"Segments processed: {self.segments_processed}")
        print(f"Entities extracted: {self.entities_extracted}")
        print(f"Entities written: {self.entities_written}")
        print(f"Relationships created: {self.relationships_created}")
        print(f"Duration: {self.duration_seconds:.2f}s")
        print(f"Cost: ${self.cost_usd:.4f}")

        if self.errors:
            print(f"\n⚠️  {len(self.errors)} errors:")
            for error in self.errors[:5]:  # Show first 5
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings[:5]:
                print(f"  - {warning}")

        if self.dry_run:
            print("\n🔍 DRY RUN - No data written to Neo4j")

        print("=" * 60)


# =================================================================
# VALIDATION RESULT
# =================================================================

@dataclass
class ValidationResult:
    """
    Result of validation and enrichment.
    """
    valid: bool
    """Overall validation result"""

    errors: List[str] = field(default_factory=list)
    """Validation errors"""

    warnings: List[str] = field(default_factory=list)
    """Validation warnings"""

    enrichments_added: int = 0
    """Number of enrichments added"""

    references_resolved: int = 0
    """Number of references resolved to existing nodes"""
