
import asyncio
import os
import logging
import sys
from pathlib import Path

# Aggiungi la directory 'src' al path di sistema per trovare i moduli
# Questo rende lo script eseguibile da qualsiasi posizione
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from neo4j import AsyncGraphDatabase
from iusgraph.document_ingestion.ingestion_pipeline import IngestionPipeline
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env nella root del progetto
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Configura un logging di base per vedere l'output della pipeline
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    """
    Funzione principale per eseguire la pipeline di ingestione.
    """
    # 1. Recupera le credenziali dalle variabili d'ambiente
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not openrouter_api_key or not neo4j_password:
        logging.error("Errore: Imposta le variabili d'ambiente nel file .env nella root del progetto.")
        return

    # 2. Crea il driver per la connessione a Neo4j
    driver = None
    try:
        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        logging.info(f"Connessione a Neo4j stabilita a {neo4j_uri}")

        # 3. Inizializza la pipeline di ingestione
        pipeline = IngestionPipeline(
            neo4j_driver=driver,
            openrouter_api_key=openrouter_api_key,
            config={} 
        )

        # 4. Definisci il percorso del file da analizzare (ora nella root)
        file_to_ingest = project_root / "documento_test.txt"
        
        if not file_to_ingest.exists():
            logging.error(f"File di test non trovato: {file_to_ingest}")
            return

        # 5. Esegui la pipeline in modalità "dry_run"
        logging.info(f"Avvio ingestione in modalità DRY RUN per il file: {file_to_ingest.name}")
        
        result = await pipeline.ingest_document(
            file_path=file_to_ingest,
            dry_run=True 
        )

        # 6. Stampa un riepilogo dei risultati
        logging.info("--- Riepilogo Ingestione (Dry Run) ---")
        result.print_summary()
        logging.info("------------------------------------")

    except Exception as e:
        logging.error(f"Si è verificato un errore durante l'esecuzione della pipeline: {e}", exc_info=True)
    finally:
        # 7. Chiudi la connessione al database
        if driver:
            await driver.close()
            logging.info("Connessione a Neo4j chiusa.")

if __name__ == "__main__":
    asyncio.run(main())
