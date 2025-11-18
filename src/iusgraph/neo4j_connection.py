"""
Neo4j Connection Manager

Centralized singleton for managing Neo4j async driver connections.
Provides connection pooling, health checks, and graceful shutdown.

Usage:
    driver = await Neo4jConnectionManager.get_driver()
    async with driver.session() as session:
        result = await session.run("MATCH (n) RETURN count(n)")
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from neo4j import AsyncGraphDatabase, AsyncDriver
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """
    Singleton connection manager for Neo4j.

    Manages a single AsyncDriver instance shared across the application,
    with configurable connection pooling and automatic health checks.
    """

    _instance: Optional['Neo4jConnectionManager'] = None
    _driver: Optional[AsyncDriver] = None
    _is_initialized: bool = False
    _loop_id: Optional[int] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(
        cls,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        max_connection_pool_size: int = 50,
        **kwargs
    ) -> AsyncDriver:
        """
        Initialize Neo4j driver with connection pooling.

        Args:
            uri: Neo4j connection URI (default: from NEO4J_URI env var)
            username: Neo4j username (default: from NEO4J_USER env var)
            password: Neo4j password (default: from NEO4J_PASSWORD env var)
            database: Database name (default: from NEO4J_DATABASE env var or "neo4j")
            max_connection_pool_size: Maximum connections in pool
            **kwargs: Additional driver configuration options

        Returns:
            AsyncDriver instance

        Raises:
            ValueError: If password is not provided
        """
        current_loop = asyncio.get_running_loop()

        if cls._is_initialized and cls._driver is not None:
            if cls._loop_id == id(current_loop):
                logger.info("Neo4j driver already initialized, returning existing driver")
                return cls._driver
            logger.info("Detected event loop mismatch, rebuilding Neo4j driver")
            await cls.close()

        # Load configuration from environment variables
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = username or os.getenv("NEO4J_USER", "neo4j")
        password = password or os.getenv("NEO4J_PASSWORD")
        database = database or os.getenv("NEO4J_DATABASE", "neo4j")

        if not password:
            raise ValueError(
                "Neo4j password is required. "
                "Provide via NEO4J_PASSWORD environment variable or password parameter."
            )

        logger.info(f"Initializing Neo4j driver: {uri} (database: {database})")

        try:
            cls._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_pool_size=max_connection_pool_size,
                connection_timeout=30,  # 30 seconds
                **kwargs
            )

            # Verify connectivity
            await cls._driver.verify_connectivity()

            cls._is_initialized = True
            cls._loop_id = id(current_loop)
            logger.info("Neo4j driver initialized successfully")

            return cls._driver

        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {str(e)}", exc_info=True)
            cls._driver = None
            cls._is_initialized = False
            raise

    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        """
        Get the Neo4j driver instance.

        Returns:
            AsyncDriver instance

        Raises:
            RuntimeError: If driver not initialized
        """
        if not cls._is_initialized or cls._driver is None:
            raise RuntimeError(
                "Neo4j driver not initialized. "
                "Call Neo4jConnectionManager.initialize() first."
            )

        return cls._driver

    @classmethod
    async def close(cls):
        """
        Close the Neo4j driver and cleanup resources.

        Should be called during application shutdown.
        """
        if cls._driver is not None:
            logger.info("Closing Neo4j driver...")
            await cls._driver.close()
            cls._driver = None
            cls._is_initialized = False
            cls._loop_id = None
            logger.info("Neo4j driver closed")
        else:
            logger.debug("Neo4j driver not initialized, nothing to close")

    @classmethod
    async def health_check(cls) -> dict:
        """
        Perform health check on Neo4j connection.

        Returns:
            dict with status, message, and optional details
        """
        if not cls._is_initialized or cls._driver is None:
            return {
                "status": "unhealthy",
                "message": "Neo4j driver not initialized",
                "details": None
            }

        try:
            # Try to verify connectivity
            await cls._driver.verify_connectivity()

            # Run a simple query to verify database access
            async with cls._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()

                if record and record["test"] == 1:
                    return {
                        "status": "healthy",
                        "message": "Neo4j connection is healthy",
                        "details": {
                            "uri": cls._driver._uri,
                            "pool_size": cls._driver._pool.size if hasattr(cls._driver, '_pool') else "unknown"
                        }
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": "Neo4j query returned unexpected result",
                        "details": None
                    }

        except Exception as e:
            logger.error(f"Neo4j health check failed: {str(e)}", exc_info=True)
            return {
                "status": "unhealthy",
                "message": f"Neo4j health check failed: {str(e)}",
                "details": {"error": str(e)}
            }

    @classmethod
    async def backup_database(cls, backup_name: Optional[str] = None, backup_dir: str = "backups") -> str:
        """
        Creates a backup of the Neo4j database by exporting all nodes and relationships.
        
        Args:
            backup_name: Optional custom name for the backup file. If None, uses timestamp.
            backup_dir: Directory where backups are stored (default: "backups")
            
        Returns:
            Path to the created backup file
            
        Raises:
            Exception: If backup fails
        """
        logger.info(f"Starting database backup: {backup_name or 'auto'}")
        try:
            await cls.initialize()
            
            # Create backup directory if it doesn't exist
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename
            if backup_name:
                # Sanitize backup name
                safe_name = "".join(c for c in backup_name if c.isalnum() or c in (' ', '-', '_')).strip()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{safe_name}_{timestamp}.cypher"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"backup_{timestamp}.cypher"
            
            backup_file_path = backup_path / filename
            
            # Export all nodes and relationships
            cypher_statements = []
            
            async with cls.session() as session:
                # Export all nodes with their properties
                nodes_query = """
                MATCH (n)
                RETURN labels(n) as labels, properties(n) as props, id(n) as node_id
                ORDER BY id(n)
                """
                nodes_result = await session.run(nodes_query)
                nodes = await nodes_result.values()
                
                for labels, props, node_id in nodes:
                    if not labels:
                        continue
                    label_str = ":".join(labels)
                    # Escape properties for Cypher
                    props_str = ", ".join([
                        f"`{k}`: {cls._format_cypher_value(v)}"
                        for k, v in props.items()
                    ])
                    # Use MERGE to allow restore even if nodes already exist
                    cypher_statements.append(
                        f"MERGE (n{node_id}:{label_str} {{{props_str}}});"
                    )
                
                # Export all relationships
                rels_query = """
                MATCH (a)-[r]->(b)
                RETURN type(r) as rel_type, properties(r) as props, 
                       id(a) as start_id, id(b) as end_id
                ORDER BY id(r)
                """
                rels_result = await session.run(rels_query)
                relationships = await rels_result.values()
                
                for rel_type, props, start_id, end_id in relationships:
                    props_str = ", ".join([
                        f"`{k}`: {cls._format_cypher_value(v)}"
                        for k, v in props.items()
                    ])
                    props_clause = f" {{{props_str}}}" if props_str else ""
                    cypher_statements.append(
                        f"MATCH (a{start_id}), (b{end_id}) "
                        f"CREATE (a{start_id})-[:{rel_type}{props_clause}]->(b{end_id});"
                    )
            
            # Write backup file
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                f.write(f"// Neo4j Backup\n")
                f.write(f"// Created: {datetime.now().isoformat()}\n")
                f.write(f"// Backup name: {backup_name or 'auto'}\n")
                f.write("// NOTE: This backup uses internal node IDs which are not persistent.\n")
                f.write("// For restore, you may need to manually adjust the MATCH clauses in relationships.\n\n")
                f.write("// Nodes\n")
                for stmt in cypher_statements:
                    if stmt.startswith("MERGE (n") or stmt.startswith("CREATE (n"):
                        f.write(stmt + "\n")
                f.write("\n// Relationships\n")
                for stmt in cypher_statements:
                    if stmt.startswith("MATCH (a"):
                        f.write(stmt + "\n")
            
            logger.info(f"Backup completed successfully: {backup_file_path}")
            return str(backup_file_path)
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _format_cypher_value(value: Any) -> str:
        """Format a Python value for Cypher syntax."""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Escape quotes and newlines
            escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            return f'"{escaped}"'
        elif isinstance(value, (list, tuple)):
            items = [Neo4jConnectionManager._format_cypher_value(item) for item in value]
            return f"[{', '.join(items)}]"
        elif isinstance(value, dict):
            items = [
                f"`{k}`: {Neo4jConnectionManager._format_cypher_value(v)}"
                for k, v in value.items()
            ]
            return f"{{{', '.join(items)}}}"
        else:
            # Fallback: convert to string
            escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'

    @classmethod
    async def reset_database(cls):
        """
        Deletes all nodes and relationships from the database.
        Ensures the driver is initialized before proceeding.
        """
        logger.warning("Resetting Neo4j database: ALL DATA WILL BE DELETED.")
        try:
            # Ensure the driver is initialized before trying to get it
            await cls.initialize()
            
            async with cls.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")
                logger.info("Database has been successfully reset.")
        except Exception as e:
            logger.error(f"Failed to reset database: {e}", exc_info=True)
            raise

    @classmethod
    @asynccontextmanager
    async def session(cls, database: Optional[str] = None):
        """
        Context manager for Neo4j sessions.

        Usage:
            async with Neo4jConnectionManager.session() as session:
                result = await session.run("MATCH (n) RETURN n")

        Args:
            database: Optional database name override

        Yields:
            AsyncSession
        """
        driver = await cls.get_driver()
        async with driver.session(database=database) as session:
            yield session

    @classmethod
    async def execute_query(cls, query: str, parameters: Optional[dict] = None, database: Optional[str] = None):
        """
        Execute a Cypher query and return results.

        Convenience method for simple queries.

        Args:
            query: Cypher query string
            parameters: Query parameters dict
            database: Optional database name

        Returns:
            List of record dictionaries
        """
        async with cls.session(database=database) as session:
            result = await session.run(query, parameters or {})
            records = [record.data() async for record in result]
            return records

    @classmethod
    async def get_database_info(cls) -> dict:
        """
        Get Neo4j database information.

        Returns:
            dict with database metadata
        """
        try:
            async with cls.session() as session:
                # Get database name
                db_result = await session.run("CALL db.info()")
                db_info = await db_result.single()

                # Get node count
                count_result = await session.run("MATCH (n) RETURN count(n) as node_count")
                count_record = await count_result.single()

                # Get relationship count
                rel_count_result = await session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
                rel_count_record = await rel_count_result.single()

                return {
                    "database_name": db_info.get("name") if db_info else "unknown",
                    "node_count": count_record["node_count"] if count_record else 0,
                    "relationship_count": rel_count_record["rel_count"] if rel_count_record else 0,
                }

        except Exception as e:
            logger.error(f"Failed to get database info: {str(e)}", exc_info=True)
            return {
                "database_name": "error",
                "node_count": -1,
                "relationship_count": -1,
                "error": str(e)
            }


# Convenience function for simple usage
async def get_neo4j_driver() -> AsyncDriver:
    """
    Get the initialized Neo4j driver.

    Convenience function wrapping Neo4jConnectionManager.get_driver()

    Returns:
        AsyncDriver instance
    """
    return await Neo4jConnectionManager.get_driver()
