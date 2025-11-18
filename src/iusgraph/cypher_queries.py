"""
Cypher Query Templates for KG Enrichment
=========================================

Optimized Cypher queries for multi-source legal knowledge graph:
- Norms (Normattiva)
- Case law (Sentenze)
- Doctrine (Academic commentary)
- Community contributions

Features:
- Intent-specific patterns
- Source-aware filtering
- Performance optimization (indexes, limits)
- Controversy detection
- Dynamic quorum support

Reference: docs/02-methodology/knowledge-graph.md (65+ relationship types)
"""

from typing import Dict, List
from enum import Enum


class IntentType(str, Enum):
    """Intent types for query selection."""
    CONTRACT_INTERPRETATION = "contract_interpretation"
    COMPLIANCE_QUESTION = "compliance_question"
    NORM_EXPLANATION = "norm_explanation"
    PRECEDENT_SEARCH = "precedent_search"


class CypherQueries:
    """
    Collection of Cypher query templates for graph enrichment.

    All queries are parameterized for safety and support Neo4j constraints.
    """

    # ==========================================
    # NORMS QUERIES (Normattiva)
    # ==========================================

    @staticmethod
    def get_norms_by_concept(limit: int = 10) -> str:
        """
        Query: Find norms related to a legal concept.

        Used for: CONTRACT_INTERPRETATION, NORM_EXPLANATION
        Returns: Norms with interpretations and principles
        """
        return f"""
        MATCH (c:ConceptoGiuridico)-[:APPLICA_A]->(n:Norma)
        WHERE c.nome CONTAINS $concept OR n.descrizione CONTAINS $concept
        OPTIONAL MATCH (n)-[:ESPRIME_PRINCIPIO]->(p:PrincipioGiuridico)
        OPTIONAL MATCH (n)-[:CONTIENE]->(cm:Comma)
        RETURN
            n.node_id as id,
            n.estremi as estremi,
            n.titolo as titolo,
            n.descrizione as descrizione,
            n.stato as stato,
            n.testo_vigente as testo_vigente,
            n.data_entrata_in_vigore as data_entrata_in_vigore,
            n.confidence as confidence,
            n.controversy_flag as controversy_flag,
            COALESCE(p.nome, '') as principio,
            COUNT(cm) as num_commi
        ORDER BY n.confidence DESC, p.livello DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_norms_with_modality(limit: int = 10) -> str:
        """
        Query: Find norms that impose obligations/prohibitions.

        Used for: COMPLIANCE_QUESTION
        Returns: Norms with modal properties (must do, cannot do, may do)
        """
        return f"""
        MATCH (n:Norma)-[:IMPONE]->(m:ModalitaGiuridica)
        WHERE m.tipo_modalita IN ['obbligo', 'divieto', 'permesso']
        AND (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
        OPTIONAL MATCH (m)-[:APPLICA_A]->(s:SoggettoGiuridico)
        RETURN
            n.node_id as id,
            n.estremi as estremi,
            n.titolo as titolo,
            n.descrizione as descrizione,
            n.stato as stato,
            m.tipo_modalita as tipo_modalita,
            m.descrizione as modalita_descrizione,
            n.data_entrata_in_vigore as data_vigore,
            n.confidence as confidence
        ORDER BY m.tipo_modalita DESC, n.confidence DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_norms_by_principle(limit: int = 10) -> str:
        """
        Query: Find norms expressing a given principle.

        Used for: NORM_EXPLANATION, COMPLIANCE_QUESTION
        Returns: Norms with their constitutional/general principles
        """
        return f"""
        MATCH (n:Norma)-[:ESPRIME_PRINCIPIO]->(p:PrincipioGiuridico)
        WHERE p.nome CONTAINS $concept OR p.descrizione CONTAINS $concept
        OPTIONAL MATCH (n)-[:DIPENDE_DA]->(n2:Norma)
        RETURN
            n.node_id as id,
            n.estremi as estremi,
            n.titolo as titolo,
            n.descrizione as descrizione,
            n.stato as stato,
            p.nome as principio,
            p.livello as principio_level,
            p.tipo as principio_type,
            n.confidence as confidence
        ORDER BY p.livello DESC, n.data_entrata_in_vigore DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_norm_versions(norm_id: str) -> str:
        """
        Query: Get version history of a norm (multivigenza).

        Returns: All versions with temporal chain
        """
        return f"""
        MATCH (n:Norma {{node_id: $norm_id}})-[:HA_VERSIONE]->(v:Versione)
        RETURN
            v.node_id as id,
            v.numero_versione as numero,
            v.data_inizio_validita as data_inizio,
            v.data_fine_validita as data_fine,
            v.testo_completo as testo,
            v.descrizione_modifiche as modifiche,
            v.fonte_modifica as fonte_modifica
        ORDER BY v.data_inizio_validita DESC
        """

    @staticmethod
    def get_norms_modified_by(modifying_norm_id: str, limit: int = 20) -> str:
        """
        Query: Find all norms modified by a given norm.

        Used for: Tracking legislative changes
        Returns: Norms with type of modification
        """
        return f"""
        MATCH (modifier:Norma {{node_id: $modifying_norm_id}})
        -[r:SOSTITUISCE|INSERISCE|ABROGA_TOTALMENTE|ABROGA_PARZIALMENTE|INTEGRA|DEROGA_A]->
        (modified:Norma)
        RETURN
            modified.node_id as id,
            modified.estremi as estremi,
            type(r) as tipo_modifica,
            r.data_efficacia as data_efficacia,
            modified.stato as stato
        LIMIT {limit}
        """

    # ==========================================
    # SENTENZE QUERIES (Case Law)
    # ==========================================

    @staticmethod
    def get_sentenze_applying_norm(norm_id: str, limit: int = 5) -> str:
        """
        Query: Find sentenze that APPLY a norm to cases.

        Used for: PRECEDENT_SEARCH, CONTRACT_INTERPRETATION
        Returns: Case law with application context
        """
        return f"""
        MATCH (a:AttoGiudiziario)-[r:APPLICA]->(n:Norma {{node_id: $norm_id}})
        OPTIONAL MATCH (a)-[:HA_VERSIONE]->(v:Versione)
        RETURN
            a.node_id as id,
            a.numero as numero,
            a.data as data,
            a.organo as organo,
            a.materia as materia,
            r.confidence as confidence,
            v.testo_completo as testo_ultima_versione,
            a.has_errata_corrige as has_errata
        ORDER BY a.data DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_sentenze_interpreting_norm(norm_id: str, limit: int = 5) -> str:
        """
        Query: Find sentenze that INTERPRET/discuss a norm's meaning.

        Used for: NORM_EXPLANATION
        Returns: Case law discussing norm interpretation
        """
        return f"""
        MATCH (a:AttoGiudiziario)-[r:INTERPRETA]->(n:Norma {{node_id: $norm_id}})
        RETURN
            a.node_id as id,
            a.numero as numero,
            a.data as data,
            a.organo as organo,
            a.tipologia as tipologia,
            r.tipo_interpretazione as tipo_interpretazione,
            r.confidence as confidence,
            r.orientamento as orientamento
        ORDER BY a.data DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_precedent_chain(sentenza_id: str) -> str:
        """
        Query: Get precedent relationship chain for a sentenza.

        Returns: OVERRULED/DISTINGUISHABLE relationships
        """
        return f"""
        MATCH (s:AttoGiudiziario {{node_id: $sentenza_id}})
        OPTIONAL MATCH (s)-[r_parent:PRECEDENTE_DI]->(parent:AttoGiudiziario)
        OPTIONAL MATCH (s)<-[r_child:PRECEDENTE_DI]-(child:AttoGiudiziario)
        OPTIONAL MATCH (s)-[:HA_VERSIONE]->(v:Versione)
        RETURN
            s.numero as numero,
            s.data as data,
            v.numero_versione as versione,
            parent.numero as parent_precedente,
            child.numero as child_seguente,
            r_parent.forza_vincolante as forza_vincolante
        """

    @staticmethod
    def get_sentenze_by_materia(limit: int = 5) -> str:
        """
        Query: Find sentenze by subject matter (materia).

        Used for: COMPLIANCE_QUESTION, PRECEDENT_SEARCH
        Returns: Case law grouped by subject
        """
        return f"""
        MATCH (a:AttoGiudiziario)
        WHERE a.materia CONTAINS $concept
        RETURN
            a.node_id as id,
            a.numero as numero,
            a.data as data,
            a.organo as organo,
            a.materia as materia,
            a.tipologia as tipologia
        ORDER BY a.data DESC
        LIMIT {limit}
        """

    # ==========================================
    # DOTTRINA QUERIES (Academic Doctrine)
    # ==========================================

    @staticmethod
    def get_doctrine_commentary(limit: int = 5) -> str:
        """
        Query: Find academic commentary on norms.

        Used for: NORM_EXPLANATION, CONTRACT_INTERPRETATION
        Returns: Curated and community-voted doctrine
        """
        return f"""
        MATCH (d:Dottrina)-[r:COMMENTA]->(n:Norma)
        WHERE n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept
        RETURN
            d.node_id as id,
            d.titolo as titolo,
            d.autore as autore,
            d.fonte as fonte,
            d.anno_pubblicazione as anno,
            r.tipo_commento as tipo_commento,
            r.confidence as confidence,
            d.citations_count as citations,
            d.source_quality as source_quality
        ORDER BY d.citations_count DESC, r.confidence DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_doctrine_by_author(limit: int = 5) -> str:
        """
        Query: Find doctrine by specific authority (e.g., Bianca, Galgano).

        Used for: Finding authoritative interpretations
        Returns: Works by specific legal scholars
        """
        return f"""
        MATCH (d:Dottrina)
        WHERE d.autore CONTAINS $autore
        RETURN
            d.node_id as id,
            d.titolo as titolo,
            d.autore as autore,
            d.fonte as fonte,
            d.anno_pubblicazione as anno,
            d.citations_count as citations
        ORDER BY d.anno_pubblicazione DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_competing_interpretations(norm_id: str) -> str:
        """
        Query: Find competing doctrine interpretations of same norm.

        Returns: Multiple doctrine nodes with INTERPRETA relationship
        """
        return f"""
        MATCH (d1:Dottrina)-[r1:INTERPRETA]->(n:Norma {{node_id: $norm_id}})
        OPTIONAL MATCH (d2:Dottrina)-[r2:INTERPRETA]->(n)
        WHERE d1.node_id < d2.node_id  // Avoid duplicates
        RETURN
            d1.titolo as dottrina1,
            d1.autore as autore1,
            r1.confidence as confidence1,
            d2.titolo as dottrina2,
            d2.autore as autore2,
            r2.confidence as confidence2
        """

    # ==========================================
    # CONTRIBUTIONS QUERIES (Community)
    # ==========================================

    @staticmethod
    def get_community_contributions(limit: int = 3) -> str:
        """
        Query: Find top-voted community contributions.

        Used for: All intent types (community insights)
        Returns: Contributions sorted by upvotes
        """
        return f"""
        MATCH (c:Contribution)-[r:INTERPRETA|COMMENTA]->(n:Norma)
        WHERE c.upvote_count > 0
        AND (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
        RETURN
            c.node_id as id,
            c.titolo as titolo,
            c.author_id as author,
            c.tipo as tipo,
            c.upvote_count as upvotes,
            c.downvote_count as downvotes,
            c.submission_date as submission_date,
            c.expert_reviewed as expert_reviewed,
            c.confidence as confidence
        ORDER BY (c.upvote_count - c.downvote_count) DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_contribution_voting_status(contribution_id: str) -> str:
        """
        Query: Get voting status for contribution in review queue.

        Returns: Vote counts and status
        """
        return f"""
        MATCH (c:Contribution {{node_id: $contribution_id}})
        RETURN
            c.node_id as id,
            c.titolo as titolo,
            c.status as status,
            c.upvote_count as upvotes,
            c.downvote_count as downvotes,
            (c.upvote_count - c.downvote_count) as net_votes,
            c.created_at as created_at,
            c.expert_reviewed as expert_reviewed
        """

    # ==========================================
    # CONTROVERSY & CONFLICT QUERIES
    # ==========================================

    @staticmethod
    def get_controversy_flags(limit: int = 10) -> str:
        """
        Query: Find norms with controversy flags.

        Returns: Norms with conflicting RLCF feedback
        """
        return f"""
        MATCH (n:Norma)
        WHERE n.controversy_flag = true
        AND (n.descrizione CONTAINS $concept OR n.estremi CONTAINS $concept)
        RETURN
            n.node_id as id,
            n.estremi as estremi,
            n.stato as stato_ufficiale,
            n.controversy_details as controversy_details,
            n.data_ultima_modifica as data_last_flag
        ORDER BY n.data_ultima_modifica DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_conflicting_interpretations(norm_id: str) -> str:
        """
        Query: Find conflicting interpretations (doctrine vs doctrine).

        Returns: Multiple INTERPRETA edges with contradictory properties
        """
        return f"""
        MATCH (d1:Dottrina)-[r1:INTERPRETA]->(n:Norma {{node_id: $norm_id}})
        MATCH (d2:Dottrina)-[r2:INTERPRETA]->(n)
        WHERE d1.node_id <> d2.node_id
        AND r1.orientamento <> r2.orientamento
        RETURN
            d1.autore as autore1,
            r1.orientamento as orientamento1,
            d2.autore as autore2,
            r2.orientamento as orientamento2,
            r1.confidence as conf1,
            r2.confidence as conf2
        """

    # ==========================================
    # RLCF & QUORUM QUERIES
    # ==========================================

    @staticmethod
    def get_edge_authority_from_rlcf(edge_id: str) -> str:
        """
        Query: Get RLCF authority scores for specific edge.

        Returns: Authority aggregation and quorum satisfaction
        """
        return f"""
        MATCH (e)-[rel]->()
        WHERE elementId(rel) = $edge_id
        RETURN
            rel.rlcf_authority_score as authority_score,
            rel.rlcf_quorum_satisfied as quorum_satisfied,
            rel.rlcf_experts as expert_count,
            rel.rlcf_created_at as created_at
        """

    @staticmethod
    def get_dynamic_quorum_threshold(source_type: str) -> Dict[str, float]:
        """
        Get dynamic quorum thresholds based on source type.

        Args:
            source_type: 'norma', 'sentenza', 'dottrina', or 'contribution'

        Returns:
            {quorum: N_experts, threshold: authority_score}
        """
        thresholds = {
            "norma": {"quorum": 3, "threshold": 0.80},
            "sentenza": {"quorum": 4, "threshold": 0.85},
            "dottrina": {"quorum": 5, "threshold": 0.75},
            "contribution": {"quorum": None, "threshold": None}  # Uses community votes
        }
        return thresholds.get(source_type, {"quorum": 3, "threshold": 0.80})

    # ==========================================
    # RELATIONSHIP CLASSIFICATION QUERIES
    # ==========================================

    @staticmethod
    def get_relationship_type_context(source_id: str, target_id: str) -> str:
        """
        Query: Determine relationship type (APPLICA vs INTERPRETA).

        Context-dependent based on document content.
        Returns: Suggested relationship type and properties
        """
        return f"""
        MATCH (a:AttoGiudiziario {{node_id: $source_id}})
        MATCH (n:Norma {{node_id: $target_id}})
        OPTIONAL MATCH (a)-[:RIGUARDA]->(c:Caso)
        OPTIONAL MATCH (c)-[:APPLICA_NORMA_A_CASO]->(n)
        RETURN
            CASE WHEN c IS NOT NULL THEN 'APPLICA'
                 ELSE 'INTERPRETA' END as suggested_relation,
            c.descrizione as caso_descrizione,
            a.materia as materia
        """

    # ==========================================
    # AUDIT & PROVENANCE QUERIES
    # ==========================================

    @staticmethod
    def get_edge_audit_trail(edge_id: str) -> str:
        """
        Query: Get full audit trail for an edge.

        Requires: PostgreSQL kg_edge_audit table join via application layer
        Returns: All sources that created/modified this edge
        """
        return f"""
        // Neo4j part: get edge properties
        MATCH (a)-[rel]->(b)
        WHERE elementId(rel) = $edge_id
        RETURN
            a.node_id as source_id,
            b.node_id as target_id,
            type(rel) as relationship_type,
            rel.source_type as source_type,
            rel.timestamp as timestamp,
            rel.confidence as confidence,
            rel.created_by as created_by
        """

    # ==========================================
    # VALIDATION QUERIES
    # ==========================================

    @staticmethod
    def validate_schema_constraints() -> List[str]:
        """
        List of Cypher constraints to enforce schema.

        Returns: Constraint creation statements
        """
        return [
            # Every Norma must have at least one Versione
            """CREATE CONSTRAINT norma_must_have_version
               FOR (n:Norma) REQUIRE (n)-[:HA_VERSIONE]->(:Versione)""",

            # Every Versione must have dates
            """CREATE CONSTRAINT versione_dates
               FOR (v:Versione) REQUIRE (v.data_inizio_validita IS NOT NULL)""",

            # Node IDs must be unique
            """CREATE CONSTRAINT unique_node_id
               FOR (n) REQUIRE n.node_id IS UNIQUE""",

            # Relationship types must be valid (enforcement via application)
        ]

    @staticmethod
    def check_integrity(node_type: str) -> str:
        """
        Query: Check data integrity for node type.

        Args:
            node_type: 'Norma', 'AttoGiudiziario', 'Dottrina', etc

        Returns: Integrity check query
        """
        if node_type == "Norma":
            return f"""
            MATCH (n:Norma)
            WHERE NOT (n)-[:HA_VERSIONE]->(:Versione)
            RETURN n.estremi as missing_version
            """
        elif node_type == "Versione":
            return f"""
            MATCH (v:Versione)
            WHERE v.data_inizio_validita IS NULL
            RETURN v.node_id as incomplete_version
            """
        else:
            return f"MATCH (n:{node_type}) RETURN count(n) as count"


# ==========================================
# Query Builder Helper
# ==========================================

class CypherQueryBuilder:
    """
    Helper to build dynamic Cypher queries.
    """

    @staticmethod
    def build_intent_specific_query(
        intent_type: IntentType,
        concept: str,
        limit: int = 10
    ) -> str:
        """
        Select appropriate query based on intent type.

        Args:
            intent_type: Classification intent
            concept: Search concept
            limit: Result limit

        Returns:
            Appropriate Cypher query
        """
        if intent_type == IntentType.CONTRACT_INTERPRETATION:
            return CypherQueries.get_norms_by_concept(limit)
        elif intent_type == IntentType.COMPLIANCE_QUESTION:
            return CypherQueries.get_norms_with_modality(limit)
        elif intent_type == IntentType.NORM_EXPLANATION:
            return CypherQueries.get_norms_by_principle(limit)
        else:  # PRECEDENT_SEARCH
            return CypherQueries.get_sentenze_applying_norm("", limit)

    @staticmethod
    def add_confidence_filter(query: str, min_confidence: float = 0.7) -> str:
        """
        Add confidence score filter to query.

        Args:
            query: Base Cypher query
            min_confidence: Minimum confidence threshold

        Returns:
            Query with confidence filter
        """
        return query.replace(
            "RETURN",
            f"WHERE n.confidence >= {min_confidence}\nRETURN"
        )

    @staticmethod
    def add_recency_filter(query: str, days: int = 365) -> str:
        """
        Add recency filter (last N days) to query.

        Args:
            query: Base Cypher query
            days: Number of days back

        Returns:
            Query with recency filter
        """
        return query.replace(
            "RETURN",
            f"WHERE datetime(n.timestamp) > datetime.now() - duration({{days: {days}}})\nRETURN"
        )
