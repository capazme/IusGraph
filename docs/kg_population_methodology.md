# Methodology for Schema-Accurate KG Population

This guide operationalizes the architecture in `ARCHITETTURA_PIPELINE.md` and the schema defined in `knowledge-graph.md`, ensuring that every ingestion path (normative and interpretative) populates the MERL-T knowledge graph with complete, validated, and provenance-rich facts.

## 1. Current Pipeline Assessment & Gap Analysis

| Pipeline Component | Expected Role (per `ARCHITETTURA_PIPELINE.md`) | Observed Gaps vs. `knowledge-graph.md` |
|--------------------|-----------------------------------------------|----------------------------------------|
| `DocumentReader` / API adapters | Produce clean segments with provenance for all flows (Fasi 1–3) | ✅ Structure is adequate; enforce minimum context (before/after) to feed validation. |
| `LLMExtractor` + prompts (`prompt_norm_*`, `prompt_exegete.txt`) | Specialized agents (Normalizzatore, Esegeta, Tassonomista) aligned with schema nodes/relations | ❌ Prompts do not enumerate canonical node/relationship types; responses diverge (e.g., `"ConcettoGiuridico"` vs. `"Concetto Giuridico"`, missing `source_label`). Need hard contract and schema dictionary. |
| `Validator` | Automatic schema, confidence, and completeness checks before Neo4j writes | ⚠ Only generic checks today; lacks node-type-specific property validation and cross-reference to existing graph (e.g., verifying `Norma` exists before `disciplina`). |
| `Neo4jWriter` | Merge nodes/edges with provenance, per Fasi 1.5, 2.5, 3.4 | ✅ Canonical merge keys exist, but assumes labels are already schema-valid; needs guardrails when key properties missing. |
| Expert supervision (Fase 4) | Route low-confidence outputs to manual review UI | ⚠ Queue + Streamlit UI referenced but not fully integrated with ingestion outputs (confidence, rationale, validator errors). |

Key blockers: (1) Missing extraction contract; (2) validator not enforcing `knowledge-graph.md` property/relationship rules; (3) lack of governance loop connecting confidence thresholds with expert approval.

## 2. Schema-Conformant Extraction Contract

### 2.1 Canonical JSON Envelope

All LLM agents must return:

```json
{
  "entities": [
    {
      "type": "Norma",
      "label": "Art. 1414 c.c.",
      "properties": {...},
      "confidence": 0.93
    }
  ],
  "relationships": [
    {
      "type": "disciplina",
      "source_label": "Art. 1414 c.c.",
      "target_label": "Simulazione",
      "properties": {...},
      "confidence": 0.91
    }
  ]
}
```

- `type` must exactly match the literal values in `NodeType`/`RelationType` (copy directly from `knowledge-graph.md`), including spaces (e.g., `"Concetto Giuridico"`, `"Modalità Giuridica"`, `"Comma/Lettera/Numero"`).
- `properties` MUST include all mandatory attributes referenced in the schema (e.g., `estremi` for `Norma`, `nome` for `Concetto Giuridico`, `tipo_interpretazione` for `interpreta` when available). Optional fields should be omitted rather than left blank.
- `confidence` is required for both entities and relationships; upstream heuristics (prompt instructions) should map LLM self-estimates to `[0, 1]`.

### 2.2 Prompt & Dictionary Requirements

1. **Schema dictionary injection**: Each prompt must embed a table extracted from `knowledge-graph.md` listing allowed node/relationship types and mandatory properties. This can be inlined once and referenced via reusable include files.
2. **Context placeholders**:
   - `__NORMA_LABEL__` and other anchor identifiers must be explicitly referenced in the instructions (“Use the provided `__NORMA_LABEL__` verbatim as the `source_label` of every `disciplina` relationship”).
   - For interpretative flows (`prompt_exegete.txt`), inject existing graph context (per Fase 2.2) and require explicit linking to pre-existing nodes using their canonical labels.
3. **Validation-ready outputs**:
   - Enforce camel-case property keys aligned with schema (`data_pubblicazione`, `tipo_interpretazione`).
   - Require `properties.provenance_pointer` (e.g., paragraph citation) whenever the prompt includes structured source metadata.
4. **LLM guardrails**:
   - Mention that any node/edge outside the allowed list must be omitted, not invented.
   - Provide negative examples showing rejection of unknown node types (e.g., `"CommentoDottrinale"`).

### 2.3 Parser Enhancements

Until prompts are fully compliant, add a normalization layer in `LLMExtractor._parse_response`:

- Map common aliases to canonical enums (e.g., `"ConcettoGiuridico" → "Concetto Giuridico"`, `"start_node_id" → `source_label``).
- Validate `properties` keys against schema dictionary; log structured warnings for missing mandatory fields so Validator can decide whether to drop or queue for human review.

## 3. Validation & Governance Layer

Building on Fase 4 (“Flusso di Supervisione”) and §5.2 of `knowledge-graph.md`, implement multi-tier validation.

### 3.1 Automated Validation (Validator Module)

- **Confidence gates**: keep dynamic thresholds per node/edge type (e.g., `0.85` for `Principio Giuridico`, `0.7` for `Comma/Lettera/Numero`). Below-threshold items are auto-routed to human queue.
- **Schema compliance**: extend `_validate_entity`/`_validate_relationship` with per-type rules:
  - `Norma`: require `estremi`, `stato`, `versione`; ensure date sequences (`data_pubblicazione` ≤ `data_entrata_in_vigore`).
  - `Concetto Giuridico`: require `nome`, optionally `definizione`.
  - `disciplina`: ensure source is `Norma` and target `Concetto Giuridico`.
  - Structural relations: verify parent-child sequencing (e.g., `contiene` only between `Norma`→`Comma/Lettera/Numero` or `Comma`→`Lettera`).
- **Reference resolution**: before writing, run Cypher checks (as suggested in `ARCHITETTURA_PIPELINE.md` Fasi 1.1–3.5) to confirm the just-created edges exist (e.g., `MATCH (:Norma {estremi: ...})-[:disciplina]->(:Concetto Giuridico)`).

### 3.2 Human-in-the-Loop Workflow

- **Review queue**: Persist low-confidence or schema-incomplete items into a “pending approvals” store (e.g., PostgreSQL table or Neo4j staging labels). Include provenance snippets, LLM rationale, validator errors.
- **Expert UI** (Streamlit per Fase 4): surfaces three actions—approve, correct, reject. Approved items feed back into the writer; corrections modify JSON first; rejections store rationale for model fine-tuning.
- **Feedback logging**: Store reviewer decisions (`validato_da`, `data_validazione`, `punteggio_qualita`) on nodes/edges per §5 of `knowledge-graph.md`.

### 3.3 Governance Policies

- **Versioned prompts & configs**: treat each prompt revision as a versioned artifact; link ingestion runs to prompt version + model for reproducibility.
- **Audit trail**: log every write to Neo4j with session ID, operator (LLM vs. human), and diff summary. Use `creato_da`, `metodo_acquisizione`, `confidence_score`.
- **Periodic schema regression tests**: run automated checks (Cypher unit tests) verifying invariants (e.g., no `disciplina` edges missing `properties.certezza`).

## 4. Execution & Monitoring Strategy

### 4.1 Implementation Roadmap

1. **Contract rollout**: update prompt files and `_parse_response` concurrently, then run dry ingest on representative articles (Art. 1414 c.c.) to confirm structural nodes and semantic relations land correctly.
2. **Validator upgrade**: implement per-type rule tables (`NODE_RULES`, `REL_RULES`) and integrate Cypher-based lookups for existing graph context.
3. **Governance layer**: stand up staging queue + Streamlit interface; integrate with Validator outputs.
4. **Backfill & migration**: reprocess historical segments to normalize node/edge types; write repair scripts to fix labels (e.g., convert dangling `"ConcettoGiuridico"` nodes).

### 4.2 Monitoring & Quality KPIs

- **Extraction metrics**: track counts per node/edge type, average confidence, schema rejection rates per agent phase (Fase 1.1–3.3).
- **Validation funnel**: monitor % auto-approved vs. queued vs. rejected; target ≥85% auto-approval once prompts stabilize.
- **Neo4j health checks**: schedule Cypher tests enumerated in `ARCHITETTURA_PIPELINE.md` to ensure expected edges exist; alert on failures.
- **Cost & performance**: log LLM usage (`cost_usd`, `tokens_*`) and correlate with quality metrics to optimize model selection.

### 4.3 Continuous Improvement

- Feed expert corrections back into prompt tuning datasets; retrain or few-shot adapt prompts monthly.
- Use RLCF data to adjust confidence thresholds and validator strictness.
- Periodically review schema coverage: ensure all 23 node types and 65 relationship types are appearing where expected; prioritize under-represented areas for agent fine-tuning (e.g., `Modalità Giuridica` extraction).

By aligning extraction, validation, and governance with the schema contract, the pipeline will consistently produce high-quality, audit-ready knowledge graph updates while preserving the expert-in-the-loop guarantees outlined in `ARCHITETTURA_PIPELINE.md`.

## 5. Implementation Notes (November 2025)

- **Schema contract helper**: `src/iusgraph/document_ingestion/schema_contract.py` now centralizes node/edge rules, prompt text snippets (`get_prompt_contract_block()`), alias maps, and confidence clamps. All prompts include the `__SCHEMA_CONTRACT__` placeholder replaced automatically by `LLMExtractor`.
- **LLM normalization**: `LLMExtractor` enforces the JSON contract, normalizes alias types, clamps confidences, accepts `start_node_id`/`end_node_id`, and exposes `extract_batch` with bounded concurrency.
- **Validator + review queue**: `validator.py` loads rule tables for per-type validation, measures metrics, and routes rejected items to a lightweight JSON queue (`data/review_queue.json`) via `review_queue.py`, ready for the Streamlit supervision UI in Fase 4.
- **Prompt updates**: All normative prompts (`prompt_norm_*`) and the exegete agent embed the schema contract and explicitly require canonical keys. This guarantees alignment with `knowledge-graph.md`.
- **Sample Cypher validations**: (run post-ingestion as smoke tests)

```
MATCH (n:Norma {estremi: "Art. 1414 c.c."})
RETURN EXISTS((n)-[:contiene]->(:`Comma/Lettera/Numero`)) AS has_commi;

MATCH (:Norma {estremi:"Art. 1414 c.c."})-[r:disciplina]->(:`Concetto Giuridico`)
RETURN count(r) > 0 AS has_concepts;

MATCH (:Dottrina {autore:"G. Verdi"})-[r:critica]->(:Norma {estremi:"Art. 1414 c.c."})
RETURN count(r) > 0 AS doctrine_links;
```

