"""
Neo4j-based Legal Knowledge Graph Builder

Adapts NormGraph's LegalKnowledgeGraph to use Neo4j as the backend
while maintaining the same interface for compatibility.

This module provides:
1. Neo4j driver management and connection pooling
2. Batch insert operations for efficient data loading (1000+ nodes)
3. Cypher query methods for graph traversal
4. Full provenance and validation tracking
5. Indexing and constraint management
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
import json

from neo4j import GraphDatabase, ManagedTransaction, Session, Transaction
from neo4j.exceptions import ServiceUnavailable, TransactionError

# Import data models from NormGraph
# These will be copied/adapted from NormGraph to this project
from .models import (
    Node, Edge, GraphMetadata, EntityType, RelationType,
    ValidationStatus, Provenance, Validation, ExtractionResult
)

logger = logging.getLogger(__name__)


class Neo4jGraphDatabase:
    """
    Neo4j database connection manager with connection pooling.

    Handles connection initialization, schema setup, and query execution.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (bolt://host:port)
            username: Neo4j username
            password: Neo4j password
            database: Database name
        """
        self.uri = uri
        self.database = database
        self.driver = None

        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            # Test connection
            with self.driver.session(database=database) as session:
                result = session.run("RETURN 1")
                logger.info(f"Connected to Neo4j at {uri}")
        except ServiceUnavailable:
            logger.error(f"Cannot connect to Neo4j at {uri}")
            raise

    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """
        Execute a read query and return results.

        Args:
            query: Cypher query
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Dict[str, Any] = None) -> Any:
        """
        Execute a write query.

        Args:
            query: Cypher query
            parameters: Query parameters

        Returns:
            Write query result
        """
        with self.driver.session(database=self.database) as session:
            return session.write_transaction(
                lambda tx: tx.run(query, parameters or {}).single()
            )

    def setup_schema(self):
        """Initialize Neo4j schema with indexes and constraints."""
        with self.driver.session(database=self.database) as session:
            # Create indexes for performance
            index_queries = [
                # Unique URN constraint
                "CREATE CONSTRAINT norma_urn IF NOT EXISTS FOR (n:Norma) REQUIRE n.urn IS UNIQUE",
                # Indexes for fast lookup
                "CREATE INDEX norma_id IF NOT EXISTS FOR (n:Norma) ON (n.norm_id)",
                "CREATE INDEX concept_name IF NOT EXISTS FOR (c:ConcettoGiuridico) ON (c.nome)",
                "CREATE INDEX article_num IF NOT EXISTS FOR (n:Norma) ON (n.article_number)",
                "CREATE INDEX validation_status IF NOT EXISTS FOR (n) ON (n.validation_status)",
            ]

            for query in index_queries:
                try:
                    session.run(query)
                    logger.debug(f"Schema operation: {query[:50]}...")
                except Exception as e:
                    # Index may already exist
                    logger.debug(f"Schema operation already exists: {e}")


class Neo4jLegalKnowledgeGraph:
    """
    Neo4j-based legal knowledge graph implementation.

    Maintains same interface as NormGraph's LegalKnowledgeGraph
    but uses Neo4j as persistence layer for scalability.

    Local caches (nodes, edges, indexes) are kept in memory
    for fast operations, with periodic sync to Neo4j.
    """

    def __init__(
        self,
        db: Neo4jGraphDatabase,
        metadata: Optional[GraphMetadata] = None,
        use_local_cache: bool = True
    ):
        """
        Initialize Neo4j-based knowledge graph.

        Args:
            db: Neo4j database connection
            metadata: Optional metadata for the graph
            use_local_cache: Keep nodes/edges in memory for fast access
        """
        self.db = db
        self.metadata = metadata or GraphMetadata()
        self.use_local_cache = use_local_cache

        # Local in-memory caches (kept in sync with Neo4j)
        self.nodes: Dict[str, Node] = {}  # id -> Node
        self.edges: Dict[str, Edge] = {}  # id -> Edge

        # Indexes for fast lookup
        self._entity_type_index: Dict[EntityType, Set[str]] = defaultdict(set)
        self._relation_type_index: Dict[RelationType, Set[str]] = defaultdict(set)
        self._article_index: Dict[str, str] = {}  # article_number -> node_id
        self._urn_index: Dict[str, str] = {}  # URN -> node_id

    def add_node(self, node: Node) -> bool:
        """
        Add a node to the graph.

        Args:
            node: Node to add

        Returns:
            True if added, False if already exists
        """
        if node.id in self.nodes:
            logger.debug(f"Node {node.id} already exists")
            return False

        # Add to local cache
        if self.use_local_cache:
            self.nodes[node.id] = node
            self._entity_type_index[node.entity_type].add(node.id)

            if node.article_number:
                self._article_index[node.article_number] = node.id

        # Persist to Neo4j
        self._persist_node_to_neo4j(node)

        # Update metadata
        self.metadata.node_count = len(self.nodes)
        if node.is_validated():
            self.metadata.validated_node_count += 1
        self.metadata.modified_at = datetime.now()

        return True

    def add_edge(self, edge: Edge) -> bool:
        """
        Add an edge to the graph.

        Args:
            edge: Edge to add

        Returns:
            True if added, False if already exists or nodes don't exist
        """
        if edge.id in self.edges:
            logger.debug(f"Edge {edge.id} already exists")
            return False

        # Check that source and target nodes exist
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            logger.warning(
                f"Cannot add edge {edge.id}: "
                f"source {edge.source_id} or target {edge.target_id} not found"
            )
            return False

        # Add to local cache
        if self.use_local_cache:
            self.edges[edge.id] = edge
            self._relation_type_index[edge.relation_type].add(edge.id)

        # Persist to Neo4j
        self._persist_edge_to_neo4j(edge)

        # Update metadata
        self.metadata.edge_count = len(self.edges)
        if edge.is_validated():
            self.metadata.validated_edge_count += 1
        self.metadata.modified_at = datetime.now()

        return True

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get an edge by ID."""
        return self.edges.get(edge_id)

    def get_nodes_by_type(self, entity_type: EntityType) -> List[Node]:
        """Get all nodes of a specific type."""
        node_ids = self._entity_type_index.get(entity_type, set())
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_edges_by_type(self, relation_type: RelationType) -> List[Edge]:
        """Get all edges of a specific type."""
        edge_ids = self._relation_type_index.get(relation_type, set())
        return [self.edges[eid] for eid in edge_ids if eid in self.edges]

    def get_node_by_article(self, article_number: str) -> Optional[Node]:
        """Get a node by article number."""
        node_id = self._article_index.get(article_number)
        if node_id:
            return self.nodes.get(node_id)
        return None

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "out",
        relation_type: Optional[RelationType] = None
    ) -> List[Node]:
        """
        Get neighboring nodes.

        Args:
            node_id: ID of the node
            direction: "out" (outgoing), "in" (incoming), or "both"
            relation_type: Filter by relationship type

        Returns:
            List of neighboring nodes
        """
        if node_id not in self.nodes:
            return []

        neighbor_ids = set()

        if direction in ["out", "both"]:
            for edge in self.edges.values():
                if edge.source_id == node_id:
                    if relation_type is None or edge.relation_type == relation_type:
                        neighbor_ids.add(edge.target_id)

        if direction in ["in", "both"]:
            for edge in self.edges.values():
                if edge.target_id == node_id:
                    if relation_type is None or edge.relation_type == relation_type:
                        neighbor_ids.add(edge.source_id)

        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]

    def calculate_statistics(self):
        """Calculate and update graph statistics."""
        # Average confidence
        all_confidences = (
            [n.confidence for n in self.nodes.values()] +
            [e.confidence for e in self.edges.values()]
        )

        if all_confidences:
            self.metadata.average_confidence = sum(all_confidences) / len(all_confidences)

        # Validation counts
        self.metadata.validated_node_count = sum(
            1 for n in self.nodes.values() if n.is_validated()
        )
        self.metadata.validated_edge_count = sum(
            1 for e in self.edges.values() if e.is_validated()
        )

        # Completeness score
        total_elements = len(self.nodes) + len(self.edges)
        validated_elements = (
            self.metadata.validated_node_count +
            self.metadata.validated_edge_count
        )

        if total_elements > 0:
            self.metadata.completeness_score = validated_elements / total_elements
        else:
            self.metadata.completeness_score = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire graph to dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    # ============================================================================
    # Neo4j Persistence Methods
    # ============================================================================

    def _persist_node_to_neo4j(self, node: Node):
        """Persist a single node to Neo4j."""
        # Determine the label based on entity type
        label = self._entity_type_to_neo4j_label(node.entity_type)

        # Prepare properties
        properties = {
            "id": node.id,
            "label": node.label,
            "description": node.description,
            "article_number": node.article_number,
            "law_reference": node.law_reference,
            "confidence": node.confidence,
            "validation_status": node.validation_status.value,
            "created_at": node.created_at.isoformat(),
            "modified_at": node.modified_at.isoformat(),
            "created_by": node.created_by,
            "modified_by": node.modified_by,
            "version": node.version,
            "attributes": json.dumps(node.attributes) if node.attributes else "{}",
            "tags": list(node.tags) if node.tags else [],
            "categories": list(node.categories) if node.categories else [],
        }

        # Add provenance as JSON
        if node.provenance:
            properties["provenance"] = json.dumps(node.provenance.to_dict())

        # Create Cypher query
        query = f"""
        CREATE (n:{label} $props)
        RETURN n
        """

        try:
            self.db.execute_write(query, {"props": properties})
            logger.debug(f"Persisted node {node.id} to Neo4j")
        except Exception as e:
            logger.error(f"Error persisting node {node.id}: {e}")
            raise

    def _persist_edge_to_neo4j(self, edge: Edge):
        """Persist a single edge to Neo4j."""
        # Relationship type from RelationType enum
        rel_type = edge.relation_type.value.upper()

        # Prepare properties
        properties = {
            "id": edge.id,
            "description": edge.description,
            "weight": edge.weight,
            "directed": edge.directed,
            "legal_basis": edge.legal_basis,
            "confidence": edge.confidence,
            "validation_status": edge.validation_status.value,
            "created_at": edge.created_at.isoformat(),
            "modified_at": edge.modified_at.isoformat(),
            "created_by": edge.created_by,
            "modified_by": edge.modified_by,
            "version": edge.version,
            "attributes": json.dumps(edge.attributes) if edge.attributes else "{}",
            "tags": list(edge.tags) if edge.tags else [],
        }

        # Add temporal validity
        if edge.temporal_validity_start:
            properties["temporal_validity_start"] = edge.temporal_validity_start.isoformat()
        if edge.temporal_validity_end:
            properties["temporal_validity_end"] = edge.temporal_validity_end.isoformat()

        # Add provenance as JSON
        if edge.provenance:
            properties["provenance"] = json.dumps(edge.provenance.to_dict())

        # Create Cypher query
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        CREATE (source)-[r:{rel_type} $props]->(target)
        RETURN r
        """

        try:
            self.db.execute_write(query, {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "props": properties
            })
            logger.debug(f"Persisted edge {edge.id} to Neo4j")
        except Exception as e:
            logger.error(f"Error persisting edge {edge.id}: {e}")
            raise

    def batch_insert_nodes(self, nodes: List[Node], batch_size: int = 1000):
        """
        Efficiently insert multiple nodes using UNWIND.

        Args:
            nodes: List of nodes to insert
            batch_size: Number of nodes per batch
        """
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            self._batch_insert_nodes_neo4j(batch)
            logger.info(f"Inserted batch of {len(batch)} nodes")

    def batch_insert_edges(self, edges: List[Edge], batch_size: int = 1000):
        """
        Efficiently insert multiple edges using UNWIND.

        Args:
            edges: List of edges to insert
            batch_size: Number of edges per batch
        """
        for i in range(0, len(edges), batch_size):
            batch = edges[i:i + batch_size]
            self._batch_insert_edges_neo4j(batch)
            logger.info(f"Inserted batch of {len(batch)} edges")

    def _batch_insert_nodes_neo4j(self, nodes: List[Node]):
        """Internal method for batch inserting nodes."""
        # Group nodes by entity type for efficient insertion
        nodes_by_type = defaultdict(list)
        for node in nodes:
            nodes_by_type[node.entity_type].append(node)

        for entity_type, nodes_group in nodes_by_type.items():
            label = self._entity_type_to_neo4j_label(entity_type)

            # Convert nodes to property dictionaries
            node_props_list = []
            for node in nodes_group:
                props = {
                    "id": node.id,
                    "label": node.label,
                    "description": node.description,
                    "article_number": node.article_number,
                    "confidence": node.confidence,
                    "validation_status": node.validation_status.value,
                    "created_at": node.created_at.isoformat(),
                }
                node_props_list.append(props)

            # Use UNWIND for batch insertion
            query = f"""
            UNWIND $nodes AS nodeProps
            CREATE (n:{label})
            SET n = nodeProps
            """

            try:
                self.db.execute_write(query, {"nodes": node_props_list})
            except Exception as e:
                logger.error(f"Error batch inserting {len(nodes_group)} nodes: {e}")
                raise

    def _batch_insert_edges_neo4j(self, edges: List[Edge]):
        """Internal method for batch inserting edges."""
        # Group edges by relation type
        edges_by_type = defaultdict(list)
        for edge in edges:
            edges_by_type[edge.relation_type].append(edge)

        for relation_type, edges_group in edges_by_type.items():
            rel_type = relation_type.value.upper()

            # Convert edges to property dictionaries
            edge_props_list = []
            for edge in edges_group:
                props = {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "id": edge.id,
                    "confidence": edge.confidence,
                    "validation_status": edge.validation_status.value,
                    "created_at": edge.created_at.isoformat(),
                }
                edge_props_list.append(props)

            # Use UNWIND for batch insertion
            query = f"""
            UNWIND $edges AS edgeProps
            MATCH (source {{id: edgeProps.source_id}})
            MATCH (target {{id: edgeProps.target_id}})
            CREATE (source)-[r:{rel_type}]->(target)
            SET r = edgeProps
            """

            try:
                self.db.execute_write(query, {"edges": edge_props_list})
            except Exception as e:
                logger.error(f"Error batch inserting {len(edges_group)} edges: {e}")
                raise

    # ============================================================================
    # Cypher Query Methods
    # ============================================================================

    def concept_to_norm_mapping(self, concept_name: str) -> List[Dict[str, Any]]:
        """
        Query: Find all norms (articles) related to a legal concept.

        Args:
            concept_name: Name of the legal concept

        Returns:
            List of norms mapped to the concept
        """
        query = """
        MATCH (c:ConcettoGiuridico {nome: $concept_name})-[:disciplina]-(n:Norma)
        RETURN n.id as norm_id, n.label as norm_label, n.article_number as article
        """

        return self.db.execute_query(query, {"concept_name": concept_name})

    def norm_hierarchy(self, norm_id: str) -> List[Dict[str, Any]]:
        """
        Query: Get hierarchical context (parent norms, child clauses).

        Args:
            norm_id: ID of the norm

        Returns:
            Hierarchical relationships
        """
        query = """
        MATCH (n:Norma {id: $norm_id})
        OPTIONAL MATCH (n)-[:PARTE_DI]->(parent)
        OPTIONAL MATCH (n)-[:CONTIENE]->(child)
        RETURN {
            norm: n.id,
            parent_norms: collect(parent.id),
            child_elements: collect(child.id)
        } as hierarchy
        """

        return self.db.execute_query(query, {"norm_id": norm_id})

    def related_concepts(self, norm_id: str) -> List[Dict[str, Any]]:
        """
        Query: Get concepts related to a norm via graph traversal.

        Args:
            norm_id: ID of the norm

        Returns:
            Related legal concepts
        """
        query = """
        MATCH (n:Norma {id: $norm_id})-[:disciplina]-(c:ConcettoGiuridico)
        RETURN c.id as concept_id, c.nome as concept_name
        """

        return self.db.execute_query(query, {"norm_id": norm_id})

    # ============================================================================
    # Helper Methods
    # ============================================================================

    @staticmethod
    def _entity_type_to_neo4j_label(entity_type: EntityType) -> str:
        """Convert EntityType enum to Neo4j label."""
        mapping = {
            EntityType.NORMA: "Norma",
            EntityType.CONCETTO_GIURIDICO: "ConcettoGiuridico",
            EntityType.PERSONA: "Persona",
            EntityType.ORGANIZZAZIONE: "Organizzazione",
            EntityType.GIURISPRUDENZA: "Giurisprudenza",
            EntityType.DOTTRINA: "Dottrina",
            EntityType.PROCEDURA: "Procedura",
            EntityType.ATTO: "Atto",
            EntityType.SENTENZA: "Sentenza",
            EntityType.CUSTOM: "Custom",
        }
        return mapping.get(entity_type, "Custom")


class Neo4jGraphBuildingStrategy(ABC):
    """Abstract base class for Neo4j-based graph building strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def build(
        self,
        extraction_result: ExtractionResult,
        graph: Neo4jLegalKnowledgeGraph,
        existing_nodes: Optional[List[Node]] = None
    ) -> Neo4jLegalKnowledgeGraph:
        """
        Build a graph from extraction results.

        Args:
            extraction_result: Extracted nodes and edges
            graph: Neo4j knowledge graph instance
            existing_nodes: Optional list of existing nodes to merge

        Returns:
            Updated Neo4jLegalKnowledgeGraph
        """
        pass


class EntityCentricNeo4jStrategy(Neo4jGraphBuildingStrategy):
    """Entity-centric graph building for Neo4j backend."""

    def __init__(self):
        super().__init__("entity_centric")

    def build(
        self,
        extraction_result: ExtractionResult,
        graph: Neo4jLegalKnowledgeGraph,
        existing_nodes: Optional[List[Node]] = None
    ) -> Neo4jLegalKnowledgeGraph:
        """Build entity-centric graph using batch insertion."""
        graph.metadata.construction_strategy = self.name

        # Batch insert all nodes
        if extraction_result.nodes:
            graph.batch_insert_nodes(extraction_result.nodes)
            # Add to local cache
            for node in extraction_result.nodes:
                graph.nodes[node.id] = node
                graph._entity_type_index[node.entity_type].add(node.id)

        # Batch insert all edges
        if extraction_result.edges:
            graph.batch_insert_edges(extraction_result.edges)
            # Add to local cache
            for edge in extraction_result.edges:
                graph.edges[edge.id] = edge
                graph._relation_type_index[edge.relation_type].add(edge.id)

        graph.calculate_statistics()
        return graph


# Export main classes
__all__ = [
    "Neo4jGraphDatabase",
    "Neo4jLegalKnowledgeGraph",
    "Neo4jGraphBuildingStrategy",
    "EntityCentricNeo4jStrategy",
]
