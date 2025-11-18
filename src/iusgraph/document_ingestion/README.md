# Document Ingestion Pipeline

LLM-based pipeline for ingesting legal documents (PDF/DOCX/TXT) into the MERL-T Knowledge Graph.

## 📋 Overview

This pipeline automatically extracts structured knowledge from unstructured legal texts using Large Language Models (Claude/GPT-4) and writes it to Neo4j according to the MERL-T Knowledge Graph schema (23 node types).

### Key Features

✅ **Multi-Format Support**: PDF, DOCX, TXT, Markdown
✅ **LLM-Based Extraction**: Uses Claude 3.5 Sonnet or GPT-4 via OpenRouter
✅ **23 Entity Types**: Full KG schema support (Norma, Concetto, Principio, etc.)
✅ **Complete Provenance**: Every entity traced to file:page:paragraph
✅ **Async Processing**: Parallel LLM calls for performance
✅ **Cost Tracking**: Monitor OpenRouter API costs
✅ **Dry Run Mode**: Test without writing to Neo4j

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.11+** with venv
2. **Neo4j** running (see Week 5 Day 1-2 setup)
3. **OpenRouter API key** (get from https://openrouter.ai/)

### Installation

```bash
# 1. Navigate to project root
cd /path/to/MERL-T_alpha

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip install pdfplumber python-docx aiohttp pyyaml python-dotenv neo4j

# 4. Set API key in .env
echo "OPENROUTER_API_KEY=your_key_here" >> .env
```

### Basic Usage

```bash
# Ingest a single PDF (dry run)
python backend/preprocessing/cli_ingest_document.py \
    --file "path/to/manual.pdf" \
    --dry-run \
    --max-segments 5

# Ingest for real (writes to Neo4j)
python backend/preprocessing/cli_ingest_document.py \
    --file "path/to/manual.pdf" \
    --max-segments 10

# Ingest entire directory
python backend/preprocessing/cli_ingest_document.py \
    --directory "data/manuals/" \
    --pattern "*.pdf"
```

---

## 📖 Usage Examples

### Test with Sample Segments

```bash
# Process only first 3 segments (good for initial testing)
python backend/preprocessing/cli_ingest_document.py \
    --file "backend/preprocessing/tests/Manuale di Diritto privato (Torrente, Schlesinger) (Z-Library).pdf" \
    --dry-run \
    --max-segments 3
```

**Expected output:**
- Extracts ~15-30 entities per segment
- Cost: ~$0.01 per segment
- Duration: ~10-15 seconds per segment

### Full Document Ingestion

```bash
# Ingest complete document (careful - costs add up!)
python backend/preprocessing/cli_ingest_document.py \
    --file "manual.pdf"
```

**Note**: A 100-page manual typically costs ~$1-2 in LLM API calls.

### Batch Processing

```bash
# Ingest all PDFs in a directory
python backend/preprocessing/cli_ingest_document.py \
    --directory "data/legal_manuals/" \
    --pattern "*.pdf" \
    --max-segments 50  # Limit per document
```

### Use Different LLM Model

```bash
# Use GPT-4 Turbo instead of Claude
python backend/preprocessing/cli_ingest_document.py \
    --file "manual.pdf" \
    --model "openai/gpt-4-turbo" \
    --max-segments 5
```

**Available models:**
- `google/gemini-2.5-flash` (default, $3/$15 per 1M tokens)
- `openai/gpt-4-turbo` ($10/$30 per 1M tokens)
- `openai/gpt-4o` ($2.5/$10 per 1M tokens)

---

## 🔧 Configuration

Configuration is in `backend/preprocessing/kg_config.yaml`:

```yaml
document_ingestion:
  llm:
    model: "google/gemini-2.5-flash"
    temperature: 0.1  # Low for consistency
    max_tokens: 4000

  extraction:
    parallel_requests: 3  # Concurrent LLM calls
    confidence_threshold: 0.7  # Min confidence

  writing:
    batch_size: 100  # Nodes per transaction
    duplicate_strategy: "merge"  # Avoid duplicates
```

---

## 📊 Output & Results

### Ingestion Result

```
============================================================
INGESTION RESULT: Manuale di Diritto privato.pdf
============================================================
Segments processed: 10
Entities extracted: 247
Entities written: 247
Relationships created: 89
Duration: 127.34s
Cost: $0.3450

✓ Success - No errors
============================================================
```

### Neo4j Data

After ingestion, check Neo4j Browser (http://localhost:7474):

```cypher
// Count nodes by type
MATCH (n)
RETURN labels(n)[0] AS type, count(*) AS count
ORDER BY count DESC;

// View recently ingested entities
MATCH (n)
WHERE n.extraction_timestamp > datetime() - duration({hours: 1})
RETURN n
LIMIT 50;

// Find entities from specific document
MATCH (n)
WHERE n.provenance_file CONTAINS "Torrente"
RETURN n.label, n.confidence, n.provenance_page
LIMIT 20;
```

---

## 🧪 Testing

### Unit Tests

```bash
# Run tests
pytest backend/preprocessing/document_ingestion/tests/ -v
```

### Manual Testing Checklist

- [ ] Test PDF extraction (check `tests/` directory for sample)
- [ ] Test DOCX extraction
- [ ] Test TXT extraction
- [ ] Verify LLM extraction (check entity types)
- [ ] Verify Neo4j writing (check constraints, indexes)
- [ ] Test dry-run mode
- [ ] Test cost tracking
- [ ] Test error handling (invalid file, API error)

---

## 📈 Performance & Costs

### Typical Performance

| Document Size | Segments | Entities | Duration | Cost (Claude 3.5) |
|---------------|----------|----------|----------|-------------------|
| 10 pages      | ~30      | ~150     | ~2 min   | ~$0.15            |
| 50 pages      | ~150     | ~750     | ~10 min  | ~$0.75            |
| 100 pages     | ~300     | ~1,500   | ~20 min  | ~$1.50            |
| 500 pages     | ~1,500   | ~7,500   | ~2 hours | ~$7.50            |

### Cost Breakdown

**Claude 3.5 Sonnet Pricing:**
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens

**Per segment (typical):**
- Input: ~500 tokens ($0.0015)
- Output: ~1000 tokens ($0.015)
- **Total: ~$0.017 per segment**

### Optimization Tips

1. **Use batch processing** (parallel_requests: 3-5)
2. **Enable caching** (cache_enabled: true)
3. **Limit segments** for testing (--max-segments 10)
4. **Use cheaper models** for drafts (gpt-4o: $2.5/$10)
5. **Set cost limits** (max_cost_per_document_usd: 5.0)

---

## 🐛 Troubleshooting

### Error: "OPENROUTER_API_KEY not set"

**Solution:**
```bash
# Add to .env file
echo "OPENROUTER_API_KEY=sk-or-v1-..." >> .env

# Or export in terminal
export OPENROUTER_API_KEY=sk-or-v1-...
```

### Error: "Neo4j connection failed"

**Solution:**
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Start Neo4j if not running
docker-compose --profile phase2 up -d neo4j

# Verify connection
docker exec merl-t-neo4j cypher-shell -u neo4j -p merl_t_password "RETURN 1;"
```

### Error: "pdfplumber not found"

**Solution:**
```bash
pip install pdfplumber
# Or use fallback
pip install PyPDF2
```

### Error: "Rate limit exceeded"

**Solution:**
- Reduce `parallel_requests` in config
- Add delays between batches
- Use cheaper model tier

### Low Extraction Quality

**Solutions:**
1. Increase `temperature` slightly (0.1 → 0.2)
2. Increase `max_tokens` (4000 → 6000)
3. Try different model (claude-3-opus for highest quality)
4. Adjust `confidence_threshold` (0.7 → 0.6)

---

## 📝 Architecture

### Component Flow

```
PDF Document
    ↓
DocumentReader (pdfplumber)
    ↓ (segments with provenance)
LLMExtractor (Claude via OpenRouter)
    ↓ (entities + relationships)
Validator (schema compliance)
    ↓ (validated entities)
Neo4jWriter (batch transactions)
    ↓
Knowledge Graph (Neo4j)
```

### File Structure

```
document_ingestion/
├── __init__.py
├── models.py              # Data models (Provenance, Entity, etc.)
├── document_reader.py     # PDF/DOCX/TXT extraction
├── llm_extractor.py       # LLM-based entity extraction
├── validator.py           # Validation & enrichment
├── neo4j_writer.py        # Write to Neo4j
├── ingestion_pipeline.py  # Orchestrator
└── README.md              # This file
```

---

## 🔮 Future Enhancements

### Phase 3+

- [ ] OCR support for scanned PDFs (Tesseract)
- [ ] Table extraction (parse legal tables)
- [ ] Image analysis (diagrams, flowcharts)
- [ ] Multi-language support (English, French legal texts)
- [ ] Active learning (feed uncertainties to RLCF)
- [ ] Fine-tuned models (domain-specific)
- [ ] Incremental updates (re-process only changed pages)
- [ ] Web UI for manual corrections
- [ ] Quality metrics dashboard

---

## 📚 References

- **Design Document**: `docs/08-iteration/DOCUMENT_INGESTION_PIPELINE_DESIGN.md`
- **KG Schema**: `docs/02-methodology/knowledge-graph.md`
- **Phase 2 Plan**: `docs/08-iteration/NEXT_STEPS.md`
- **Neo4j Setup**: `docs/08-iteration/WEEK5_DAY1-2_NEO4J_SETUP.md`

---

## 💬 Support

For questions or issues:
1. Check troubleshooting section above
2. Review logs in terminal output
3. Check Neo4j logs: `docker logs merl-t-neo4j`
4. Review configuration in `kg_config.yaml`

---

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: November 5, 2025
