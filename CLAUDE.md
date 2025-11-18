# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IusGraph is a legal knowledge graph system that extracts structured legal knowledge from Italian legal documents (norms, jurisprudence, doctrine) and builds a Neo4j graph database following the MERL-T schema with 23+ node types. The system uses LLM-based pipelines to transform unstructured legal text into a rich semantic graph.

## Core Architecture

### Two-Pipeline Design

The system uses a **separation and integration** strategy with two distinct ingestion flows:

1. **Normative Pipeline** (`src/iusgraph/normative_pipeline.py`): Ingests written law from the VisualEx API
   - Multi-step LLM orchestration (Structure → Concepts → Jurisprudence → Ratio)
   - Handles abrogated articles with special metadata
   - Builds hierarchical classification from Brocardi position data
   - Batched jurisprudence extraction for cost optimization

2. **Interpretive Pipeline** (`src/iusgraph/document_ingestion/ingestion_pipeline.py`): Ingests doctrinal texts (manuals, commentaries)
   - Document reading (PDF/DOCX/TXT via pdfplumber, python-docx)
   - Graph-aware context augmentation
   - Links interpretive nodes to existing normative structure

### Key Components

- **LLM Extractor** (`src/iusgraph/document_ingestion/llm_extractor.py`): Async OpenRouter API client with structured JSON extraction and cost tracking
- **Neo4j Writer** (`src/iusgraph/document_ingestion/neo4j_writer.py`): Batch transactions with MERGE logic to avoid duplicates
- **Schema Contract** (`src/iusgraph/document_ingestion/schema_contract.py`): MERL-T knowledge graph schema (23 node types, relationship types)
- **Experiment Logger** (`src/iusgraph/experiment_logger.py`): Scientific logging of all pipeline runs with full LLM interaction history
- **VisualEx API Client** (`src/iusgraph/visualex_api_client.py`): Fetches Italian legal norms from Normattiva/EUR-Lex/Brocardi

## Knowledge Graph Schema

The MERL-T schema (`knowledge-graph.md`) defines 23+ node types including:
- **Norma**: Legal norms with multivigenza (temporal versioning) support
- **Comma/Lettera/Numero**: Sub-article granular elements
- **Concetto Giuridico**: Abstract legal concepts (e.g., "Simulazione", "Buona fede")
- **Principio Giuridico**: Legal principles expressed by norms
- **Atto Giudiziario**: Judicial acts and case law
- **Dottrina**: Doctrinal commentary and scholarship
- **Versione**: Temporal versions of norms for multivigenza tracking
- **Direttiva/Regolamento UE**: EU legal acts
- **Organo Giurisdizionale**: Courts and administrative bodies
- **Caso/Fatto**: Concrete legal case patterns
- **Termine/Scadenza**: Legal deadlines and time limits
- **Sanzione**: Penalties and sanctions

## Development Commands

### Environment Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Create .env file with:
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=merltgraph2025
# OPENROUTER_API_KEY=your_key_here
```

### Neo4j Database

```bash
# Start Neo4j via Docker
docker-compose up -d

# Stop Neo4j
docker-compose down

# Access Neo4j Browser
open http://localhost:7474
# Username: neo4j
# Password: merltgraph2025

# View Neo4j logs
docker logs iusgraph-neo4j
```

### Running the Streamlit App

```bash
# From project root
streamlit run app/streamlit_app.py

# The app will be available at http://localhost:8501
```

### VisualEx API (Separate Service)

```bash
# Start VisualEx API
cd VisuaLexAPI/src
python app.py
# UI at http://localhost:5000

# Alternative: API with /api/* prefix + Swagger
cd VisuaLexAPI/src
python -m visualex_api.app
# Swagger at http://localhost:5000/api/docs
```

## Code Architecture Details

### Normative Pipeline Flow (Phase 1)

For each article (e.g., Art. 1414 c.c.), the pipeline executes:

1. **Step 1.1 - Structure Extraction** (LLM Call #1)
   - Input: `article_text`
   - Extracts: `Norma` nodes + `Comma/Lettera/Numero` with hierarchy
   - Relations: `contiene`, `parte_di`

2. **Step 1.2 - Concepts Extraction** (LLM Call #2)
   - Input: `article_text` + `brocardi_info` (brocardi, ratio, spiegazione)
   - Extracts: `Concetto Giuridico` nodes
   - Relations: `disciplina` (with certezza property)

3. **Step 1.3 - Jurisprudence Extraction** (LLM Call #3, batched)
   - Input: `brocardi_info.massime` (batched, configurable size)
   - Extracts: `Atto Giudiziario` nodes
   - Relations: `interpreta` (with tipo_interpretazione, orientamento)
   - Each batch tracked with stage_label

4. **Step 1.4 - Ratio Legis Extraction** (LLM Call #4)
   - Input: `brocardi_info.ratio`
   - Extracts: `Principio Giuridico` nodes
   - Relations: `esprime_principio` (with certezza, confidence_score)

5. **Step 1.5 - Hierarchical Classification** (No LLM, deterministic)
   - Input: `brocardi_info.position` (e.g., "Codice Civile > LIBRO QUARTO > ...")
   - Parses into hierarchy of `Concetto Giuridico` nodes with `schema: "brocardi_position"`
   - Relations: `species` (between levels), `classifica_in` (from Norma)

### Abrogation Detection

The normative pipeline detects abrogated articles early and creates minimal NORMA nodes with abrogation metadata, skipping LLM extraction for concepts/ratio/jurisprudence.

### Data Models

All extraction uses Pydantic models (`src/iusgraph/document_ingestion/models.py`):
- `DocumentSegment`: Text chunks with provenance
- `ExtractedEntity`: Node data (type, label, properties)
- `ExtractedRelationship`: Edge data (source, target, type, properties)
- `ExtractionResult`: Complete extraction with entities, relationships, cost, tokens, LLM metadata

### Neo4j Connection Management

Uses singleton pattern (`Neo4jConnectionManager` in `src/iusgraph/neo4j_connection.py`):
- Async driver initialization
- Connection pooling
- Automatic health checks and reconnection
- Thread-safe for Streamlit

### Experiment Tracking

Every pipeline run is logged to `experiments/{pipeline_type}/{timestamp}_{id}/`:
- `experiment.json`: Complete data (metadata, config, steps, LLM interactions, outputs)
- `config.json`: Quick reference configuration
- `llm_interactions.jsonl`: Line-delimited LLM calls for streaming analysis
- `summary.md`: Human-readable markdown summary

Use `ExperimentLogger` to compare experiments, analyze costs, and track model performance.

## Prompt Management

Prompts are stored as separate `.txt` files in `src/iusgraph/document_ingestion/`:
- `prompt_norm_1_structure.txt`
- `prompt_norm_2_concepts.txt` (or `prompt_norm_2a_concept_keywords.txt`)
- `prompt_norm_3_jurisprudence.txt`
- `prompt_norm_4_ratio.txt`

The Streamlit app allows editing prompts in the UI and saving them back to disk for reproducible experiments.

## Important Implementation Notes

### Avoid Code Duplication

Always check for existing functions before implementing new ones. This codebase has:
- Shared LLM extraction logic in `LLMExtractor`
- Common Neo4j operations in `Neo4jWriter`
- Reusable validation in `Validator`
- Shared models in `models.py`

### LLM Cost Optimization

- Use batching for jurisprudence extraction (configurable batch size in Streamlit)
- Track costs with `ExtractionResult.cost_usd` and experiment logs
- Use cheaper models for testing (gemini-2.5-flash default)
- Implement confidence thresholds to reduce unnecessary LLM calls

### Neo4j Best Practices

- Always use MERGE for nodes/relationships to avoid duplicates
- Set `duplicate_strategy: "merge"` in config
- Batch transactions (default 100 nodes per transaction)
- Use indexes on `node_id`, `estremi`, `URN` for performance
- Add provenance to all extracted entities

### Async/Await Patterns

The codebase uses async extensively:
- LLM API calls are async via aiohttp
- Neo4j driver supports async operations
- Streamlit requires nest_asyncio for event loop compatibility
- Use `asyncio.gather()` for parallel LLM calls

### Confidence and Review Queue

Entities with `confidence < 0.85` (configurable) go to review queue for human validation:
- `src/iusgraph/document_ingestion/review_queue.py`
- Expert approval/correction/rejection
- Decisions logged for future fine-tuning

## File Structure

```
IusGraph/
├── app/
│   └── streamlit_app.py           # Main Streamlit UI
├── src/iusgraph/
│   ├── normative_pipeline.py      # "Il Normalizzatore" agent
│   ├── visualex_api_client.py     # API client for legal norms
│   ├── experiment_logger.py       # Scientific experiment tracking
│   ├── neo4j_connection.py        # Singleton Neo4j manager
│   ├── document_ingestion/
│   │   ├── llm_extractor.py       # Async LLM extraction
│   │   ├── neo4j_writer.py        # Batch graph writes
│   │   ├── models.py              # Pydantic data models
│   │   ├── schema_contract.py     # MERL-T schema definition
│   │   ├── ingestion_pipeline.py  # Interpretive pipeline
│   │   ├── review_queue.py        # Human-in-the-loop review
│   │   ├── validator.py           # Schema validation
│   │   └── prompt_norm_*.txt      # LLM prompts
│   └── config/
│       └── kg_config.py           # Configuration management
├── VisuaLexAPI/                   # Separate API service (Quart)
│   ├── src/app.py                 # Main API + UI
│   └── src/visualex_api/app.py    # API with /api/* prefix
├── experiments/                   # Scientific logs
│   ├── normative/                 # Normative pipeline runs
│   └── interpretive/              # Interpretive pipeline runs
├── docker-compose.yml             # Neo4j container
├── requirements.txt               # Python dependencies
├── knowledge-graph.md             # MERL-T schema documentation
└── ARCHITETTURA_PIPELINE.md       # Detailed architecture guide
```

## VisualEx API

Separate Quart-based API for fetching Italian legal norms:

**Key endpoints:**
- `POST /fetch_norma_data`: Create norma structure from parameters
- `POST /fetch_article_text`: Fetch article text in parallel
- `POST /fetch_brocardi_info`: Retrieve Brocardi annotations
- `POST /fetch_all_data`: Combined text + Brocardi info
- `POST /fetch_tree`: Get article tree for complete URN
- `POST /export_pdf`: Export to PDF (requires ChromeDriver)

**Two modes:**
1. Root endpoints (`src/app.py`): UI + API at root
2. Prefixed endpoints (`src/visualex_api/app.py`): `/api/*` + Swagger UI

**Dependencies:** Normattiva, EUR-Lex, Brocardi (scraping-based, may break with HTML changes)

## Validation Queries

After ingestion, use these Cypher queries to validate the graph:

```cypher
// Count nodes by type
MATCH (n) RETURN labels(n)[0] AS type, count(*) AS count ORDER BY count DESC;

// Verify normative structure for an article
MATCH (n:Norma {estremi:"Art. 1414 c.c."})
RETURN EXISTS((n)-[:contiene]->()) AS has_structure;

// Check concept extraction
MATCH (:Norma {estremi:"Art. 1414 c.c."})-[:disciplina]->(c:`Concetto Giuridico`)
RETURN count(c) > 0 AS has_concepts;

// Verify jurisprudence links
MATCH (a:`Atto Giudiziario`)-[:interpreta]->(n:Norma {estremi:"Art. 1414 c.c."})
RETURN count(a) > 0 AS has_jurisprudence;

// Check hierarchical classification
MATCH (:Norma {estremi:"Art. 1414 c.c."})-[:classifica_in]->(c:`Concetto Giuridico`)
WHERE c.schema = "brocardi_position"
RETURN count(c) > 0 AS has_classification;

// Find recent extractions
MATCH (n) WHERE n.extraction_timestamp > datetime() - duration({hours: 1})
RETURN n LIMIT 50;
```

## Common Patterns

### Adding a New LLM Step

1. Add prompt file: `src/iusgraph/document_ingestion/prompt_norm_X_name.txt`
2. Update `NormativePipeline.run_pipeline()` with new step
3. Define extraction schema in prompt using JSON format
4. Parse response in pipeline with error handling
5. Add to `all_results` list
6. Update validation queries in tests

### Modifying Schema

1. Update `knowledge-graph.md` with new node/relationship types
2. Update `schema_contract.py` with NodeType/RelationType enums
3. Update LLM prompts to include new types
4. Add Neo4j constraints/indexes for new properties
5. Update validation logic in `Validator`

### Debugging LLM Extractions

Use the Streamlit "🔍 LLM Debug" expander to view:
- Exact prompts sent to LLM
- Raw JSON responses
- Parsing errors
- Token counts and costs
- Model used for each step
