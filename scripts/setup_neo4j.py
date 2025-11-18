
import os
import logging
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Configura un logging di base
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_neo4j_schema():
    """
    Applica lo schema, i vincoli e gli indici al database Neo4j.
    Legge i comandi dal file neo4j_schema.cypher e li esegue.
    """
    # Carica le variabili d'ambiente dal file .env nella root del progetto
    project_root = Path(__file__).parent.parent
    dotenv_path = project_root / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    # Recupera le credenziali per Neo4j
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        logging.error("Errore: La password di Neo4j non è impostata. Controlla il file .env.")
        return

    # Leggi il file dello schema (che si trova nella stessa cartella dello script)
    schema_file = Path(__file__).parent / "neo4j_schema.cypher"
    if not schema_file.exists():
        logging.error(f"File dello schema non trovato: {schema_file}")
        return

    logging.info(f"Lettura dello schema da: {schema_file}")
    schema_content = schema_file.read_text(encoding='utf-8')

    # Pulisci e dividi i comandi Cypher
    # Rimuovi i commenti e dividi per punto e virgola
    commands = [
        cmd.strip() 
        for line in schema_content.splitlines() 
        if not line.strip().startswith('//')
        for cmd in line.split(';')
        if cmd.strip()
    ]

    if not commands:
        logging.warning("Nessun comando Cypher da eseguire trovato nel file dello schema.")
        return

    logging.info(f"Trovati {len(commands)} comandi Cypher da eseguire.")

    # Connettiti a Neo4j ed esegui i comandi
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        logging.info(f"Connessione a Neo4j ({uri}) stabilita con successo.")

        with driver.session() as session:
            for i, command in enumerate(commands, 1):
                try:
                    logging.info(f"Esecuzione comando {i}/{len(commands)}: `{command[:80]}...`")
                    # Usiamo `run` che è appropriato per comandi DDL come CREATE CONSTRAINT/INDEX
                    session.run(command)
                except Exception as e:
                    # Alcuni errori sono attesi se l'indice/vincolo esiste già (IF NOT EXISTS)
                    # ma logghiamo comunque per sicurezza.
                    logging.warning(f"Attenzione durante l'esecuzione del comando {i}: {e}")

        logging.info("Configurazione dello schema Neo4j completata con successo!")

    except Exception as e:
        logging.error(f"Errore critico durante la configurazione di Neo4j: {e}", exc_info=True)
    finally:
        if driver:
            driver.close()
            logging.info("Connessione a Neo4j chiusa.")

if __name__ == "__main__":
    setup_neo4j_schema()
