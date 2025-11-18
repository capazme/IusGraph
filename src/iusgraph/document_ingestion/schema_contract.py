"""
Schema Contract Utilities
=========================

Provides canonical node/relationship metadata derived from `knowledge-graph.md`
so that extraction prompts, parsers, and validators share a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Dict, List, Optional, Tuple

from .models import NodeType, RelationType


@dataclass(frozen=True)
class NodeRule:
    """Validation rule for a node type."""

    required_properties: Tuple[str, ...] = ()
    optional_properties: Tuple[str, ...] = ()
    confidence_threshold: float = 0.7


@dataclass(frozen=True)
class RelationRule:
    """Validation rule for a relationship type."""

    source_types: Tuple[NodeType, ...] = ()
    target_types: Tuple[NodeType, ...] = ()
    required_properties: Tuple[str, ...] = ()
    confidence_threshold: float = 0.7


NODE_TYPE_RULES: Dict[NodeType, NodeRule] = {
    NodeType.NORMA: NodeRule(
        required_properties=("estremi",),
        optional_properties=(
            "titolo",
            "stato",
            "versione",
            "data_pubblicazione",
        ),
        confidence_threshold=0.85,
    ),
    NodeType.CONCETTO_GIURIDICO: NodeRule(
        required_properties=("nome",),
        optional_properties=("definizione", "ambito_di_applicazione"),
    ),
    NodeType.COMMA_LETTERA_NUMERO: NodeRule(
        required_properties=("posizione", "testo"),
        confidence_threshold=0.8,
    ),
    NodeType.ATTO_GIUDIZIARIO: NodeRule(
        required_properties=("estremi",),
        optional_properties=("organo_emittente", "data"),
        confidence_threshold=0.8,
    ),
    NodeType.DOTTRINA: NodeRule(
        required_properties=("titolo",),
        optional_properties=("autore", "data_pubblicazione"),
    ),
    NodeType.PRINCIPIO_GIURIDICO: NodeRule(
        required_properties=("nome",),
        optional_properties=("tipo", "descrizione"),
        confidence_threshold=0.85,
    ),
}


RELATION_TYPE_RULES: Dict[RelationType, RelationRule] = {
    RelationType.CONTIENE: RelationRule(
        source_types=(NodeType.NORMA, NodeType.COMMA_LETTERA_NUMERO),
        target_types=(NodeType.COMMA_LETTERA_NUMERO,),
        required_properties=("certezza",),
    ),
    RelationType.PARTE_DI: RelationRule(
        source_types=(NodeType.COMMA_LETTERA_NUMERO,),
        target_types=(NodeType.NORMA, NodeType.COMMA_LETTERA_NUMERO),
    ),
    RelationType.DISCIPLINA: RelationRule(
        source_types=(NodeType.NORMA,),
        target_types=(NodeType.CONCETTO_GIURIDICO,),
        required_properties=("certezza",),
        confidence_threshold=0.8,
    ),
    RelationType.INTERPRETA: RelationRule(
        source_types=(NodeType.ATTO_GIUDIZIARIO,),
        target_types=(NodeType.NORMA,),
        required_properties=("tipo_interpretazione",),
    ),
    RelationType.ESPRIME_PRINCIPIO: RelationRule(
        source_types=(NodeType.NORMA, NodeType.ATTO_GIUDIZIARIO),
        target_types=(NodeType.PRINCIPIO_GIURIDICO,),
        confidence_threshold=0.85,
    ),
    RelationType.SPECIES: RelationRule(
        source_types=(NodeType.CONCETTO_GIURIDICO,),
        target_types=(NodeType.CONCETTO_GIURIDICO,),
    ),
}


NODE_TYPE_ALIASES: Dict[str, NodeType] = {
    "ConcettoGiuridico": NodeType.CONCETTO_GIURIDICO,
    "PrincipioGiuridico": NodeType.PRINCIPIO_GIURIDICO,
    "AttoGiudiziario": NodeType.ATTO_GIUDIZIARIO,
    "Dottrina": NodeType.DOTTRINA,
    "Comma": NodeType.COMMA_LETTERA_NUMERO,
    "Comma/Lettera": NodeType.COMMA_LETTERA_NUMERO,
    "Lettera": NodeType.COMMA_LETTERA_NUMERO,
    "Numero": NodeType.COMMA_LETTERA_NUMERO,
}


RELATION_TYPE_ALIASES: Dict[str, RelationType] = {
    "disciplina": RelationType.DISCIPLINA,
    "interpreta": RelationType.INTERPRETA,
    "esprime_principio": RelationType.ESPRIME_PRINCIPIO,
    "species": RelationType.SPECIES,
    "contiene": RelationType.CONTIENE,
    "parte_di": RelationType.PARTE_DI,
    "discute": RelationType.DISCUTE,
}


def clamp_confidence(confidence: Optional[float], fallback: float = 0.7) -> float:
    """Normalize a confidence value to [0, 1]."""
    if confidence is None:
        return fallback
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, value))


def get_prompt_contract_block() -> str:
    """
    Generate a concise schema contract block for LLM prompts.

    Contains canonical names of entity/relationship types plus required properties.
    """
    entity_lines = []
    for node_type, rule in NODE_TYPE_RULES.items():
        req = ", ".join(rule.required_properties) or "—"
        entity_lines.append(f"- {node_type.value}: obbligatorie [{req}]")

    relation_lines = []
    for rel_type, rule in RELATION_TYPE_RULES.items():
        req = ", ".join(rule.required_properties) or "—"
        sources = ", ".join(t.value for t in rule.source_types) or "qualsiasi"
        targets = ", ".join(t.value for t in rule.target_types) or "qualsiasi"
        relation_lines.append(
            f"- {rel_type.value}: ({sources}) → ({targets}); obbligatorie [{req}]"
        )

    block = f"""
    ### Contratto di estrazione MERL-T

    **Formato obbligatorio:** JSON con chiavi `entities` e `relationships`.
    - Ogni entità: `type`, `label`, `properties`, `confidence`.
    - Ogni relazione: `type`, `source_label`, `target_label`, `properties`, `confidence`.

    **Tipi di entità principali:**
    {chr(10).join(entity_lines)}

    **Tipi di relazioni principali:**
    {chr(10).join(relation_lines)}
    """

    return dedent(block).strip()


def get_node_rule(node_type: NodeType) -> Optional[NodeRule]:
    return NODE_TYPE_RULES.get(node_type)


def get_relation_rule(relation_type: RelationType) -> Optional[RelationRule]:
    return RELATION_TYPE_RULES.get(relation_type)

