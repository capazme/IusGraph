# IusGraph

Experimental pipeline for populating a legal knowledge graph from Italian court decisions.

Takes a *sentenza* as input, extracts entities and relations, and loads them into a graph database. Includes a Streamlit front-end for exploration and a Docker Compose setup for the backing services.

**Status: experimental** — a research spike, not production software.

## Documentation

- [Pipeline architecture](ARCHITETTURA_PIPELINE.md) *(Italian)*
- [KG population methodology](docs/kg_population_methodology.md)

## Quick start

```bash
docker-compose up -d
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Author

Guglielmo Puzio ([@capazme](https://github.com/capazme)) — [capazme.github.io](https://capazme.github.io)
