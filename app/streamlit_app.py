

from dotenv import load_dotenv
load_dotenv()

import nest_asyncio
nest_asyncio.apply()

import sys
from pathlib import Path

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import os
import asyncio
import logging
import json
import time
from datetime import datetime

# Clear Streamlit's cache to ensure latest code is used
st.cache_data.clear()
st.cache_resource.clear()

from src.iusgraph.document_ingestion.document_reader import DocumentReader
from src.iusgraph.document_ingestion.llm_extractor import LLMExtractor
from src.iusgraph.document_ingestion.neo4j_writer import Neo4jWriter
from src.iusgraph.document_ingestion.ingestion_pipeline import IngestionPipeline
from src.iusgraph.normative_pipeline import NormativePipeline
from src.iusgraph.neo4j_connection import Neo4jConnectionManager
from src.iusgraph.visualex_api_client import VisualexApiClient
from src.iusgraph.experiment_logger import ExperimentLogger, PipelineStep, LLMInteraction

# --- Configurazione di base ---
st.set_page_config(layout="wide", page_title="IusGraph Ingestion Engine")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Gestione dello stato ---
if 'logger' not in st.session_state:
    st.session_state.logger = logging.getLogger(__name__)

# --- Funzioni di caching ---
async def initialize_neo4j_driver():
    """Initializes the Neo4j driver using the singleton manager."""
    st.session_state.logger.info("Initializing Neo4j Driver via Manager...")
    try:
        # The manager is a singleton, so this will only truly initialize once.
        driver = await Neo4jConnectionManager.initialize(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        return driver
    except Exception as e:
        st.error(f"Fatal Error: Could not initialize Neo4j Driver. {e}")
        st.stop()

@st.cache_resource
def get_llm_extractor():
    st.session_state.logger.info("Initializing LLM Extractor...")
    return LLMExtractor(api_key=os.getenv("OPENROUTER_API_KEY"))

@st.cache_data
def load_prompt(prompt_path):
    try:
        return Path(prompt_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        st.error(f"Prompt file not found at: {prompt_path}")
        return ""


def render_llm_debug(results, title):
    """Render prompts/responses for each LLM call inside an expander."""
    if not results:
        return

    with st.expander(title, expanded=False):
        for idx, result in enumerate(results, start=1):
            stage_label = result.segment.metadata.get("stage_label") if result.segment and result.segment.metadata else None
            heading = stage_label or f"Segmento {idx}"
            st.markdown(f"### {heading}")
            st.caption(f"Model: `{result.llm_model}` • Segment ID: `{result.segment.segment_id}`")

            if result.error:
                st.error(f"LLM extraction error: {result.error}")

            st.markdown("**Prompt inviato**")
            st.code(result.prompt or "[prompt vuoto]", language="markdown")

            st.markdown("**Risposta grezza**")
            st.code(result.raw_response or "[risposta vuota]", language="json")
            st.markdown("---")

# --- Funzioni di esecuzione pipeline ---
async def run_interpretive_pipeline(files):
    start_total_time = time.time()
    st.session_state.logger.info(f"Starting interpretive ingestion for {len(files)} files.")
    
    driver = await initialize_neo4j_driver()
    extractor = get_llm_extractor()
    writer = Neo4jWriter(driver)
    reader = DocumentReader()
    
    pipeline = IngestionPipeline(reader, extractor, writer)
    
    results_placeholder = st.empty()
    summary_placeholder = st.empty()
    
    with st.spinner("Processing..."):
        results = await pipeline.run_batch_pipeline(
            files,
            prompt_template_override=st.session_state.prompt_exegete
        )
        
        total_duration = time.time() - start_total_time
        total_cost = sum(r.cost_usd for r in results if r)
        
        summary_text = f"**Interpretive Ingestion Complete!**\n- **Files Processed:** {len(results)}\n- **Total Duration:** {total_duration:.2f}s\n- **Total Estimated Cost:** ${total_cost:.4f}"
        summary_placeholder.success(summary_text)
        results_placeholder.json([r.to_dict() for r in results if r])
        render_llm_debug(results, "Dettaglio LLM (Esegeta)")

async def run_normative_pipeline(article_id: str):
    start_total_time = time.time()
    st.session_state.logger.info(f"Starting normative ingestion for article: {article_id}")

    driver = await initialize_neo4j_driver()
    extractor = get_llm_extractor()
    writer = Neo4jWriter(driver)
    pipeline = NormativePipeline(
        extractor,
        writer,
        jurisprudence_batch_size=st.session_state.get("jurisprudence_batch_size", 5),
    )
    api_client = VisualexApiClient()

    st.info(f"Calling VisualexAPI for **{article_id}**...")
    api_data = await api_client.get_data_for_article(article_id)

    if not api_data or "error" in api_data:
        st.error(f"Failed to fetch data from VisualexAPI: {api_data.get('error', 'Unknown error')}")
        return

    st.success(f"Data received from VisualexAPI for **{article_id}**.")
    with st.expander("API Data Received"):
        st.json(api_data)

    prompts_config = {
        'structure': st.session_state.prompt_norm_1,
        'concept_keywords': st.session_state.get('prompt_norm_2a', st.session_state.prompt_norm_2a if 'prompt_norm_2a' in st.session_state else load_prompt("src/iusgraph/document_ingestion/prompt_norm_2a_concept_keywords.txt")),
        'concepts': st.session_state.prompt_norm_2,
        'jurisprudence': st.session_state.prompt_norm_3,
        'ratio': st.session_state.prompt_norm_4,
    }
    models_config = {
        'structure': st.session_state.model_norm_1,
        'concepts': st.session_state.model_norm_2,
        'jurisprudence': st.session_state.model_norm_3,
        'ratio': st.session_state.model_norm_4,
    }

    results_placeholder = st.empty()
    summary_placeholder = st.empty()

    with st.spinner(f"Processing normative pipeline for {article_id}..."):
        results = await pipeline.run_pipeline(
            api_data,
            prompts_config,
            models_config,
            article_label=article_id,
        )
        
        total_duration = time.time() - start_total_time
        total_cost = sum(r.cost_usd for r in results if r)
        
        summary_text = f"**Normative Ingestion Complete!**\n- **Article Processed:** {article_id}\n- **Total Duration:** {total_duration:.2f}s\n- **Total Estimated Cost:** ${total_cost:.4f}"
        summary_placeholder.success(summary_text)
        results_placeholder.json([r.to_dict() for r in results if r])
        render_llm_debug(results, "Dettaglio LLM (Normalizzatore)")

async def run_normative_pipeline_with_payload(api_payload, is_range=False):
    """
    Esegue la pipeline normativa usando un payload API personalizzato.
    L'API gestisce internamente i range e restituisce una lista di articoli.
    LOGS EVERYTHING as a structured experiment for scientific analysis.
    """
    start_total_time = time.time()
    st.info(f"🚀 Starting normative ingestion...")
    
    # Initialize experiment logger
    exp_logger = ExperimentLogger()
    
    # Prepare config
    prompts_config = {
        'structure': st.session_state.prompt_norm_1,
        'concept_keywords': st.session_state.get('prompt_norm_2a', st.session_state.prompt_norm_2a if 'prompt_norm_2a' in st.session_state else load_prompt("src/iusgraph/document_ingestion/prompt_norm_2a_concept_keywords.txt")),
        'concepts': st.session_state.prompt_norm_2,
        'jurisprudence': st.session_state.prompt_norm_3,
        'ratio': st.session_state.prompt_norm_4,
    }
    models_config = {
        'structure': st.session_state.model_norm_1,
        'concepts': st.session_state.model_norm_2,
        'jurisprudence': st.session_state.model_norm_3,
        'ratio': st.session_state.model_norm_4,
    }
    
    # Create experiment
    experiment = exp_logger.create_experiment(
        pipeline_type="normative",
        input_data=api_payload,
        models_config=models_config,
        prompts_config=prompts_config,
        parameters={
            "jurisprudence_batch_size": st.session_state.get("jurisprudence_batch_size", 5),
            "is_range": is_range,
        }
    )
    
    driver = await initialize_neo4j_driver()
    extractor = get_llm_extractor()
    writer = Neo4jWriter(driver)
    pipeline = NormativePipeline(
        extractor,
        writer,
        jurisprudence_batch_size=st.session_state.get("jurisprudence_batch_size", 5),
    )
    # Initialize API client with extended timeout for range requests
    timeout = 600 if is_range else 120  # 10 minutes for ranges, 2 minutes for single articles
    api_client = VisualexApiClient(timeout=timeout)

    if is_range:
        st.warning(f"⏱️ Range request may take several minutes. The API needs to scrape each article individually. Timeout: {timeout}s")
    
    st.info(f"📡 Calling VisualexAPI with article: `{api_payload['article']}`...")
    
    try:
        # Chiama l'API con il payload completo
        api_response = await api_client.get_data_for_articles_payload(api_payload)

        if not api_response or "error" in api_response:
            error_msg = f"Failed to fetch data from VisualexAPI: {api_response.get('error', 'Unknown error')}"
            st.error(f"❌ {error_msg}")
            experiment.error_message = error_msg
            exp_logger.save_experiment(experiment)
            return

        # L'API restituisce una lista di articoli
        articles_data = api_response if isinstance(api_response, list) else [api_response]
        
        # Deduplica articoli basandosi sul numero_articolo
        seen_articles = set()
        unique_articles = []
        duplicates = []
        
        for article_data in articles_data:
            article_id = article_data.get("norma_data", {}).get("numero_articolo", None)
            if article_id and article_id not in seen_articles:
                seen_articles.add(article_id)
                unique_articles.append(article_data)
            elif article_id:
                duplicates.append(article_id)
        
        articles_data = unique_articles
        
        st.success(f"✅ Data received from VisualexAPI: **{len(articles_data)} articoli unici**")
        
        if duplicates:
            st.warning(f"⚠️ Rimossi {len(duplicates)} duplicati: {', '.join(duplicates)}")
        
        # Mostra la lista degli articoli ricevuti
        article_ids = [art.get("norma_data", {}).get("numero_articolo", "Unknown") for art in articles_data]
        st.info(f"📋 **Articoli ricevuti:** {', '.join(article_ids)}")
        
        if is_range:
            st.info(f"📦 L'API ha trovato **{len(articles_data)} articoli** nel range richiesto")
        
        with st.expander(f"📋 API Response ({len(articles_data)} articoli)", expanded=False):
            for idx, article_data in enumerate(articles_data, 1):
                article_id = article_data.get("norma_data", {}).get("numero_articolo", "Unknown")
                st.markdown(f"### {idx}. Articolo {article_id}")
                st.json(article_data)

        # Processa ogni articolo
        progress_bar = st.progress(0)
        status_text = st.empty()
        all_results = []
        
        for idx, article_data in enumerate(articles_data, 1):
            article_id = article_data.get("article_id", f"Art. {idx}")
            status_text.text(f"🔄 Processing {idx}/{len(articles_data)}: {article_id}")
            
            step_start = time.time()
            
            try:
                results = await pipeline.run_pipeline(
                    api_data=article_data,
                    prompts=prompts_config,
                    models=models_config,
                    article_label=article_id,
                )
                all_results.extend(results)
                
                # Log each pipeline step
                for result in results:
                    step = PipelineStep(
                        step_id=f"{article_id}_{result.segment.metadata.get('stage_label', 'unknown')}",
                        step_name=result.segment.metadata.get('stage_label', 'Unknown Step'),
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat(),
                        duration_seconds=result.duration_seconds,
                        entities_extracted=len(result.entities),
                        relationships_extracted=len(result.relationships),
                    )
                    
                    # Log LLM interaction
                    interaction = LLMInteraction(
                        step_name=result.segment.metadata.get('stage_label', 'Unknown'),
                        model=result.llm_model,
                        prompt=result.prompt,
                        raw_response=result.raw_response,
                        tokens_input=result.tokens_input,
                        tokens_output=result.tokens_output,
                        cost_usd=result.cost_usd,
                        duration_seconds=result.duration_seconds,
                        timestamp=datetime.now().isoformat(),
                        error=result.error,
                    )
                    step.llm_interactions.append(interaction)
                    
                    if result.error:
                        step.errors.append(result.error)
                    
                    experiment.steps.append(step)
                
                # Scrivi nel grafo
                await writer.write_extraction_results(results)
                
                progress_bar.progress(idx / len(articles_data))
                st.success(f"✅ Completed {article_id}")
                
            except Exception as e:
                error_msg = f"Error processing {article_id}: {e}"
                st.error(f"❌ {error_msg}")
                
                # Log error step
                error_step = PipelineStep(
                    step_id=f"{article_id}_error",
                    step_name=f"Error: {article_id}",
                    start_time=datetime.now().isoformat(),
                    end_time=datetime.now().isoformat(),
                    duration_seconds=time.time() - step_start,
                    errors=[str(e)],
                )
                experiment.steps.append(error_step)
                
                if not st.checkbox(f"Continue after error on {article_id}?", value=True, key=f"continue_{idx}"):
                    experiment.error_message = error_msg
                    break
        
        status_text.text(f"✅ Completed! Processed {idx}/{len(articles_data)} articles")
        
        elapsed = time.time() - start_total_time
        st.success(f"🎉 Normative ingestion completed in {elapsed:.2f}s")
        st.info(f"📊 Total results: {len(all_results)}")
        
        # Save experiment
        exp_logger.save_experiment(experiment)
        
        # Show experiment info
        with st.expander("📊 Experiment Saved", expanded=True):
            st.success(f"**Experiment ID:** `{experiment.experiment_id}`")
            st.info(f"**Location:** `experiments/normative/{experiment.experiment_id}/`")
            st.json({
                "duration_seconds": experiment.total_duration_seconds,
                "cost_usd": experiment.total_cost_usd,
                "tokens_input": experiment.total_tokens_input,
                "tokens_output": experiment.total_tokens_output,
                "entities": experiment.total_entities,
                "relationships": experiment.total_relationships,
            })
        
        # Mostra debug per tutti gli articoli
        render_llm_debug(all_results, "Dettaglio LLM (Normalizzatore - Batch)")
        
    except Exception as e:
        experiment.error_message = str(e)
        exp_logger.save_experiment(experiment)
        st.error(f"❌ Fatal error: {e}")
        raise

# --- Interfaccia Utente ---
st.title("IusGraph Ingestion Engine")

# --- Pannello di Controllo Laterale ---
with st.sidebar:
    st.header("⚙️ Config")
    
    # --- Backup Section ---
    with st.expander("💾 Database Backup", expanded=False):
        backup_name = st.text_input(
            "Backup Name (optional)",
            value="",
            help="Enter a custom name for the backup. If empty, a timestamp will be used.",
            placeholder="e.g., pre_reset_backup"
        )
        if st.button("📦 Create Backup", use_container_width=True):
            with st.spinner("Creating backup..."):
                try:
                    # Attempt to get the current event loop
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        # If no loop is running in this thread, create a new one for this task
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    backup_path = loop.run_until_complete(
                        Neo4jConnectionManager.backup_database(
                            backup_name=backup_name if backup_name.strip() else None
                        )
                    )
                    st.success(f"✅ Backup created successfully!")
                    st.info(f"📁 Location: `{backup_path}`")
                except Exception as e:
                    st.error(f"❌ Failed to create backup: {e}")
    
    # --- Reset Section ---
    with st.expander("🗑️ Reset DB", expanded=False):
        st.warning("⚠️ Elimina tutto!")
        if st.button("🔥 Format", type="secondary", use_container_width=True):
            with st.spinner("..."):
                try:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    loop.run_until_complete(Neo4jConnectionManager.reset_database())
                    st.success("✅ Done!")
                except Exception as e:
                    st.error(f"❌ {e}")
    
    # --- Experiments Section ---
    with st.expander("🔬 Experiments", expanded=False):
        exp_logger = ExperimentLogger()
        experiments = exp_logger.list_experiments("normative")
        
        if experiments:
            st.caption(f"**Total runs:** {len(experiments)}")
            
            # Show last 5 experiments
            for exp in experiments[:5]:
                with st.container():
                    st.caption(f"**{exp['experiment_id']}**")
                    st.caption(f"Status: {exp['status']} | Cost: ${exp['cost_usd']:.4f}")
                    st.caption(f"Entities: {exp['entities']} | Rels: {exp['relationships']}")
                    st.divider()
        else:
            st.caption("No experiments yet")
    
    st.divider()
    st.caption("**Modelli:**")
    st.caption("• gemini-2.5-flash")
    st.caption("• gpt-4o / gpt-4-turbo")
    st.caption("• claude-3-haiku")

# --- Interfaccia a Schede ---
tab_normative, tab_interpretive = st.tabs(["Ingestione Normativa (Normalizzatore)", "Ingestione Interpretativa (Esegeta)"])

with tab_normative:
    st.header("Normalizzatore")
    
    # --- Form Strutturato per Inserimento Norma ---
    st.subheader("📝 Norma da estrarre")
    
    col1, col2 = st.columns(2)
    
    with col1:
        act_type = st.selectbox(
            "Tipo di atto",
            options=[
                "",
                "codice civile",
                "codice penale",
                "codice di procedura civile",
                "codice di procedura penale",
                "costituzione",
                "preleggi",
                "legge",
                "decreto legge",
                "decreto legislativo",
                "Regolamento UE",
                "Direttiva UE",
                "TUE",
                "TFUE",
                "CDFUE",
                "codice della navigazione",
                "codice della strada",
                "codice del consumo",
                "codice dei contratti pubblici",
                "codice antimafia",
                "codice della crisi d'impresa e dell'insolvenza",
            ],
            index=1,  # Default: codice civile
            help="Seleziona il tipo di atto normativo"
        )
    
    with col2:
        act_number = st.text_input(
            "Numero atto",
            value="",
            placeholder="es. 262 (per leggi/decreti)",
            help="Numero dell'atto (opzionale per i codici)"
        )
    
    col3, col4 = st.columns(2)
    
    with col3:
        act_date = st.text_input(
            "Data atto",
            value="",
            placeholder="gg/mm/aaaa",
            help="Data dell'atto (opzionale per i codici)"
        )
    
    with col4:
        use_range = st.checkbox(
            "Range di articoli",
            value=False,
            help="Seleziona per estrarre più articoli consecutivi"
        )
    
    if use_range:
        col5, col6 = st.columns(2)
        with col5:
            article_start = st.text_input(
                "Articolo iniziale",
                value="1414",
                help="Primo articolo del range (es. '1414' o '1414-bis')"
            )
        with col6:
            article_end = st.text_input(
                "Articolo finale",
                value="1416",
                help="Ultimo articolo del range (es. '1416' o '1416-ter'). L'API gestirà automaticamente bis, ter, etc."
            )
        
        article_range = f"{article_start}-{article_end}"
        st.info(f"📦 **Range richiesto:** `{article_range}`")
        st.caption("ℹ️ L'API includerà automaticamente TUTTI gli articoli nel range, inclusi bis, ter, quater, quinquies, etc. Es: '1-10' includerà 1, 1-bis, 1-ter, 2, 2-bis, ..., 10, 10-bis, etc.")
    else:
        article_number = st.text_input(
            "Numero articolo",
            value="1414",
            help="Numero dell'articolo da estrarre (es. '1414' o '1414-bis')"
        )
        article_range = None
    
    # Costruisci il payload per l'API
    # L'API gestirà internamente il range e restituirà tutti gli articoli (inclusi bis, ter, etc.)
    api_payload = {
        "act_type": act_type,
        "article": article_range if use_range else article_number,
        "act_number": act_number if act_number else None,
        "date": act_date if act_date else None,
    }
    
    # Mostra il payload compatto
    if use_range:
        st.caption(f"→ Range: `{article_range}` da `{act_type}`")
    else:
        st.caption(f"→ Articolo: `{article_number}` da `{act_type}`")
    
    st.markdown("---")
    
    # --- Configurazione Modelli e Prompts ---
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("⚙️ Modelli LLM")
        st.session_state.model_norm_1 = st.text_input("Struttura", value=st.session_state.get("model_norm_1", "google/gemini-2.5-flash"), key="m1", label_visibility="visible")
        st.session_state.model_norm_2 = st.text_input("Concetti", value=st.session_state.get("model_norm_2", "google/gemini-2.5-flash"), key="m2", label_visibility="visible")
        st.session_state.model_norm_3 = st.text_input("Giurisprudenza", value=st.session_state.get("model_norm_3", "google/gemini-2.5-flash"), key="m3", label_visibility="visible")
        st.session_state.model_norm_4 = st.text_input("Ratio", value=st.session_state.get("model_norm_4", "google/gemini-2.5-flash"), key="m4", label_visibility="visible")
        
        st.session_state.jurisprudence_batch_size = st.number_input(
            "Batch massime",
            min_value=1,
            max_value=20,
            value=st.session_state.get("jurisprudence_batch_size", 5),
            step=1,
            key="jurisprudence_batch_input",
        )
    
    with col_right:
        st.subheader("📝 Prompts")
        prompt_tabs = st.tabs(["1️⃣ Struttura", "2️⃣ Concetti", "3️⃣ Giurisprudenza", "4️⃣ Ratio"])
        
        with prompt_tabs[0]:
            st.session_state.prompt_norm_1 = st.text_area("Prompt Struttura", load_prompt("src/iusgraph/document_ingestion/prompt_norm_1_structure.txt"), height=200, key="p1", label_visibility="collapsed")
        
        with prompt_tabs[1]:
            st.caption("2a: Keywords")
            st.session_state.prompt_norm_2a = st.text_area("Prompt Keywords", load_prompt("src/iusgraph/document_ingestion/prompt_norm_2a_concept_keywords.txt"), height=150, key="p2a", label_visibility="collapsed")
            st.caption("2b: Concetti Formali")
            st.session_state.prompt_norm_2 = st.text_area("Prompt Concetti", load_prompt("src/iusgraph/document_ingestion/prompt_norm_2_concepts.txt"), height=150, key="p2", label_visibility="collapsed")
        
        with prompt_tabs[2]:
            st.session_state.prompt_norm_3 = st.text_area("Prompt Giurisprudenza", load_prompt("src/iusgraph/document_ingestion/prompt_norm_3_jurisprudence.txt"), height=200, key="p3", label_visibility="collapsed")
        
        with prompt_tabs[3]:
            st.session_state.prompt_norm_4 = st.text_area("Prompt Ratio", load_prompt("src/iusgraph/document_ingestion/prompt_norm_4_ratio.txt"), height=200, key="p4", label_visibility="collapsed")
    
    
    # --- Avvio ---
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        if st.button("▶️ Avvia Estrazione", type="primary", use_container_width=True):
            article_input = article_range if use_range else article_number
            if act_type and article_input:
                asyncio.run(run_normative_pipeline_with_payload(api_payload, use_range))
        else:
                st.error("Compila tutti i campi obbligatori.")
    
    with col_btn2:
        with st.popover("📋 Info"):
            articles_summary = f"Range: {article_range}" if use_range else f"Art. {article_number}"
            st.caption(f"**Norma:** {act_type} - {articles_summary}")
            st.caption(f"**Modello:** {st.session_state.get('model_norm_1', 'N/A')}")
            st.caption(f"**Batch:** {st.session_state.get('jurisprudence_batch_size', 5)}")

with tab_interpretive:
    st.header("Agente 'Esegeta': Ingestione da Documenti (PDF)")
    st.markdown("Questo agente analizza documenti non strutturati per estrarre la conoscenza interpretativa e collegarla al grafo.")
    
    st.session_state.model_exegete = st.text_input(
        "Modello LLM (Esegeta)",
        value=st.session_state.get("model_exegete", "google/gemini-2.5-flash"),
        key="m_exe"
    )
    st.session_state.prompt_exegete = st.text_area("Prompt (Esegeta)", load_prompt("src/iusgraph/document_ingestion/prompt_exegete.txt"), height=300, key="p_exe")

    uploaded_files = st.file_uploader("Carica uno o più file PDF", type="pdf", accept_multiple_files=True)

    if st.button("Avvia Ingestione Interpretativa", type="primary"):
        if uploaded_files:
            temp_paths = []
            temp_dir = Path("./temp_uploads")
            temp_dir.mkdir(exist_ok=True)
            for uploaded_file in uploaded_files:
                temp_path = temp_dir / uploaded_file.name
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_paths.append(temp_path)
            
            asyncio.run(run_interpretive_pipeline(temp_paths))
        else:
            st.warning("Per favore, carica almeno un file PDF.")
