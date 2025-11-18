"""
Normative Ingestion Pipeline
=============================

Orchestrates the ingestion of normative data from the API, using a
multi-step, LLM-based approach to map the data to the rich
knowledge graph schema.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from .document_ingestion.llm_extractor import LLMExtractor
from .document_ingestion.neo4j_writer import Neo4jWriter
from .document_ingestion.models import (
    DocumentSegment,
    Provenance,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    NodeType,
    RelationType,
)
from .document_ingestion.schema_contract import get_prompt_contract_block

logger = logging.getLogger(__name__)

class NormativePipeline:
    """
    Implements the "Normalizzatore" agent workflow.
    """

    def __init__(
        self,
        extractor: LLMExtractor,
        writer: Neo4jWriter,
        jurisprudence_batch_size: int = 5,
    ):
        self.extractor = extractor
        self.writer = writer
        self.logger = logger
        self.schema_contract_block = get_prompt_contract_block()
        self.jurisprudence_batch_size = max(1, jurisprudence_batch_size)

    async def run_pipeline(
        self,
        api_data: Dict[str, Any],
        prompts: Dict[str, str],
        models: Dict[str, str],
        article_label: Optional[str] = None,
    ) -> List[ExtractionResult]:
        """
        Executes the full 4-step normative ingestion pipeline.

        Args:
            api_data: The data for a single article from the normative API.
            prompts: A dictionary containing the prompt strings for each step.
                     Keys: 'structure', 'concepts', 'jurisprudence', 'ratio'.
            models: A dictionary mapping each step to a specific LLM model.
                    Keys: 'structure', 'concepts', 'jurisprudence', 'ratio'.

        Returns:
            A list of ExtractionResult objects from each step.
        """
        all_results = []
        norma_label = self._derive_norma_label(api_data, article_label)
        position_path = self._parse_position_path(api_data)
        
        # Create a dummy segment for provenance tracking
        # In this pipeline, the "text" is the structured API data
        provenance = Provenance(source_file=f"API: {norma_label}")
        segment = DocumentSegment(text=json.dumps(api_data, indent=2), provenance=provenance)

        # --- Early Detection: Check for Abrogated Articles ---
        article_text = api_data.get("article_text", "")
        abrogation_info = self._detect_abrogation(article_text)
        
        if abrogation_info:
            self.logger.info(f"⚠️ Detected abrogated article: {norma_label}")
            self.logger.info(f"   Abrogated by: {abrogation_info['abrogating_law_type']} {abrogation_info['abrogating_law_date']}, n. {abrogation_info['abrogating_law_number']}")
            
            # Create minimal result with NORMA node + abrogation metadata
            abrogation_result = self._create_abrogated_article_result(
                norma_label=norma_label,
                abrogation_info=abrogation_info,
                provenance=provenance
            )
            all_results.append(abrogation_result)
            
            # Still create hierarchical structure
            classification_result = self._build_position_classification(
                position_path=position_path,
                norma_label=norma_label,
                provenance=provenance,
            )
            if classification_result:
                all_results.append(classification_result)
            
            # Skip LLM extraction steps (no concepts, ratio, jurisprudence)
            self.logger.info("Skipping LLM extraction for abrogated article")
            return all_results

        # --- Passo 1.1: Estrazione Strutturale ---
        self.logger.info("Fase 1.1: Estrazione Strutturale...")
        structure_segment = DocumentSegment(
            text=api_data.get("article_text", ""),
            provenance=provenance,
            metadata={"known_labels": [norma_label], "stage_label": "Fase 1.1 - Struttura"},
        )
        structure_result = await self.extractor.extract_from_segment(
            segment=structure_segment,
            prompt_template=prompts['structure'],
            model_override=models['structure'],
            context_data={
                "NORMA_LABEL": norma_label,
                "SCHEMA_CONTRACT": self.schema_contract_block,
            }
        )
        all_results.append(structure_result)

        # --- Passo 1.2: Estrazione dei Concetti (Two-Step) ---
        self.logger.info("Fase 1.2: Estrazione dei Concetti (two-step approach)...")
        
        # Passo 1.2a: Estrazione Keywords dalle Massime
        self.logger.info("Fase 1.2a: Estrazione keywords dai massime...")
        massime_list = self._collect_massime(api_data)
        concept_keywords = []
        
        if massime_list:
            keywords_segment = DocumentSegment(
                text=json.dumps(massime_list, ensure_ascii=False),
                provenance=provenance,
                metadata={"stage_label": "Fase 1.2a - Keywords Concetti"}
            )
            self.logger.info("Note: Warnings about 'Unknown entity type' in this step are expected - we extract keywords from raw response")
            keywords_result = await self.extractor.extract_from_segment(
                segment=keywords_segment,
                prompt_template=prompts['concept_keywords'],
                model_override=models['concepts'],
                context_data={
                    "MASSIME": json.dumps(massime_list, ensure_ascii=False)
                }
            )
            # Parse keywords from response (bypasses entity/relationship parsing)
            concept_keywords = self._extract_keywords_from_response(keywords_result.raw_response)
            self.logger.info(f"✓ Extracted {len(concept_keywords)} concept keywords: {concept_keywords[:5]}{'...' if len(concept_keywords) > 5 else ''}")
        else:
            self.logger.info("No massime available, skipping keyword extraction")
        
        # Passo 1.2b: Estrazione Formale dei Concetti
        self.logger.info("Fase 1.2b: Estrazione formale dei concetti...")
        concept_data = {
            "article_text": api_data.get("article_text", ""),
            "brocardi": api_data.get("brocardi_info", {}).get("Brocardi", []),
            "ratio": api_data.get("brocardi_info", {}).get("Ratio", ""),
            "spiegazione": api_data.get("brocardi_info", {}).get("Spiegazione", ""),
            "concept_keywords": concept_keywords
        }
        concepts_segment = DocumentSegment(
            text=json.dumps(concept_data, indent=2, ensure_ascii=False),
            provenance=provenance,
            metadata={"known_labels": [norma_label], "stage_label": "Fase 1.2b - Concetti Formali"},
        )
        concepts_result = await self.extractor.extract_from_segment(
            segment=concepts_segment,
            prompt_template=prompts['concepts'],
            model_override=models['concepts'],
            context_data={
                "NORMA_LABEL": norma_label,
                "JSON_DATA_TO_ANALYZE": json.dumps(concept_data, ensure_ascii=False),
                "SCHEMA_CONTRACT": self.schema_contract_block,
            }
        )
        all_results.append(concepts_result)

        # --- Passo 1.3: Estrazione della Giurisprudenza (con concordanza concetti) ---
        self.logger.info("Fase 1.3: Estrazione della Giurisprudenza...")
        # Estrai i label dei concetti per passarli al prompt giurisprudenza
        extracted_concept_labels = [entity.label for entity in concepts_result.entities]
        self.logger.info(f"Passing {len(extracted_concept_labels)} concept labels to jurisprudence extraction")
        
        jurisprudence_payload = self._collect_massime(api_data)
        jurisprudence_results = await self._run_jurisprudence_batches(
            jurisprudence_payload,
            norma_label,
            prompts['jurisprudence'],
            models['jurisprudence'],
            provenance,
            batch_size=self.jurisprudence_batch_size,
            extracted_concepts=extracted_concept_labels,
        )
        all_results.extend(jurisprudence_results)

        # --- Passo 1.4: Estrazione della Ratio Legis ---
        self.logger.info("Fase 1.4: Estrazione della Ratio Legis...")
        ratio_text = api_data.get("brocardi_info", {}).get("Ratio", "")
        ratio_segment = DocumentSegment(
            text=ratio_text,
            provenance=provenance,
            metadata={"known_labels": [norma_label], "stage_label": "Fase 1.4 - Ratio"},
        )
        ratio_result = await self.extractor.extract_from_segment(
            segment=ratio_segment,
            prompt_template=prompts['ratio'],
            model_override=models['ratio'],
            context_data={
                "NORMA_LABEL": norma_label,
                "SCHEMA_CONTRACT": self.schema_contract_block,
            }
        )
        all_results.append(ratio_result)
        
        # --- Passo extra: Classificazione gerarchica (position) ---
        classification_result = self._build_position_classification(
            position_path=position_path,
            norma_label=norma_label,
            provenance=provenance,
        )
        if classification_result:
            all_results.append(classification_result)

        # --- Scrittura sul Grafo ---
        self.logger.info("Scrittura dei risultati aggregati sul grafo...")
        await self.writer.write_extraction_results(all_results)

        return all_results

    def _collect_massime(self, api_data: Dict[str, Any]) -> List[str]:
        massime = api_data.get("massime")
        if not massime:
            massime = api_data.get("brocardi_info", {}).get("Massime", [])
        
        # Handle None case (e.g., abrogated articles)
        if massime is None:
            return []
        
        normalized = [
            entry.strip()
            for entry in massime
            if isinstance(entry, str) and entry.strip()
        ]
        return normalized

    def _detect_abrogation(self, article_text: str) -> Optional[Dict[str, str]]:
        """
        Detect if article is abrogated and extract metadata.
        
        Args:
            article_text: The text of the article
            
        Returns:
            Dict with abrogation info if detected, None otherwise:
            - is_abrogated: bool
            - abrogating_law_type: str (e.g., "L.", "D.L.")
            - abrogating_law_date: str
            - abrogating_law_number: str
        """
        import re
        
        # Pattern for: "ARTICOLO ABROGATO DALLA L. 8 MARZO 1975, N. 39"
        pattern = r'ARTICOLO ABROGATO DALLA\s+([A-Z\.]+)\s+(\d+\s+[A-Z]+\s+\d{4}),?\s*N\.\s*(\d+)'
        match = re.search(pattern, article_text, re.IGNORECASE)
        
        if match:
            return {
                "is_abrogated": True,
                "abrogating_law_type": match.group(1),
                "abrogating_law_date": match.group(2),
                "abrogating_law_number": match.group(3)
            }
        
        return None

    def _create_abrogated_article_result(
        self,
        norma_label: str,
        abrogation_info: Dict[str, str],
        provenance: Provenance
    ) -> ExtractionResult:
        """
        Create extraction result for abrogated article with metadata.
        
        Args:
            norma_label: Label of the abrogated article
            abrogation_info: Dict with abrogation metadata
            provenance: Provenance information
            
        Returns:
            ExtractionResult with NORMA nodes and ABROGA relationship
        """
        # Create NORMA node with abrogation flag
        norma_entity = ExtractedEntity(
            type=NodeType.NORMA,
            label=norma_label,
            properties={
                "estremi": norma_label,
                "abrogato": True,
                "data_abrogazione": abrogation_info["abrogating_law_date"],
                "abrogato_da_tipo": abrogation_info["abrogating_law_type"],
                "abrogato_da_numero": abrogation_info["abrogating_law_number"],
                "fonte": "brocardi_api"
            },
            confidence=1.0,
            provenance=provenance
        )
        
        # Create abrogating law label
        abrogating_law_label = f"{abrogation_info['abrogating_law_type']} {abrogation_info['abrogating_law_date']}, n. {abrogation_info['abrogating_law_number']}"
        
        # Create NORMA node for abrogating law
        abrogating_law_entity = ExtractedEntity(
            type=NodeType.NORMA,
            label=abrogating_law_label,
            properties={
                "estremi": abrogating_law_label,
                "tipo_atto": abrogation_info["abrogating_law_type"],
                "numero": abrogation_info["abrogating_law_number"],
                "data": abrogation_info["abrogating_law_date"],
                "fonte": "abrogazione_reference"
            },
            confidence=0.95,
            provenance=provenance
        )
        
        # Create ABROGA relationship
        abrogation_relationship = ExtractedRelationship(
            source_label=abrogating_law_label,
            target_label=norma_label,
            type=RelationType.ABROGA_TOTALMENTE,
            properties={
                "tipo_modifica": "abrogazione",
                "data": abrogation_info["abrogating_law_date"]
            },
            confidence=0.95,
            provenance=provenance
        )
        
        # Create result
        segment = DocumentSegment(
            text=f"Articolo abrogato da {abrogating_law_label}",
            provenance=provenance,
            metadata={"stage_label": "Abrogation Detection"}
        )
        
        return ExtractionResult(
            segment=segment,
            entities=[norma_entity, abrogating_law_entity],
            relationships=[abrogation_relationship],
            raw_response="",
            prompt="",
            llm_model="rule_based",
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            duration_seconds=0.0
        )

    async def _run_jurisprudence_batches(
        self,
        massime: List[str],
        norma_label: str,
        prompt_template: str,
        model_name: str,
        provenance: Provenance,
        batch_size: int = 5,
        extracted_concepts: Optional[List[str]] = None,
    ) -> List[ExtractionResult]:
        """
        Process massime in batches, extracting jurisprudence and concordance with concepts.
        
        Args:
            massime: List of massime texts
            norma_label: Label of the norm being processed
            prompt_template: Prompt template for extraction
            model_name: LLM model to use
            provenance: Provenance information
            batch_size: Number of massime per batch
            extracted_concepts: List of concept labels for concordance (optional)
            
        Returns:
            List of ExtractionResult objects, one per batch
        """
        if not massime:
            return []

        results = []
        for batch_index in range(0, len(massime), batch_size):
            batch = massime[batch_index:batch_index + batch_size]
            segment = DocumentSegment(
                text=json.dumps(batch, indent=2),
                provenance=provenance,
                metadata={
                    "known_labels": [norma_label],
                    "stage_label": f"Fase 1.3 - Giurisprudenza (batch {batch_index // batch_size + 1})",
                },
            )
            
            # Prepare context data with extracted concepts for concordance
            context_data = {
                "NORMA_LABEL": norma_label,
                "JSON_DATA_TO_ANALYZE": json.dumps(batch, ensure_ascii=False),
                "SCHEMA_CONTRACT": self.schema_contract_block,
                "EXTRACTED_CONCEPTS": json.dumps(extracted_concepts or [], ensure_ascii=False),
            }
            
            result = await self.extractor.extract_from_segment(
                segment=segment,
                prompt_template=prompt_template,
                model_override=model_name,
                context_data=context_data
            )
            results.append(result)
        return results

    def _derive_norma_label(
        self,
        api_data: Dict[str, Any],
        fallback: Optional[str] = None,
    ) -> str:
        norma_data = api_data.get("norma_data") or {}
        candidates = [
            norma_data.get("estremi"),
            norma_data.get("titolo"),
            norma_data.get("label"),
        ]
        numero = norma_data.get("numero_articolo")
        tipo_atto = norma_data.get("tipo_atto")
        if tipo_atto and numero:
            candidates.append(f"{tipo_atto.title()}, art. {numero}")
        article_id = api_data.get("article_id") or fallback
        if article_id:
            candidates.append(article_id)
        article_text = api_data.get("article_text") or ""
        if article_text:
            first_line = article_text.strip().splitlines()[0]
            if first_line:
                candidates.append(first_line.strip(" ."))

        for candidate in candidates:
            if candidate and candidate.strip() and candidate.strip().upper() != "N/A":
                return candidate.strip()
        return "Norma Sconosciuta"

    def _parse_position_path(self, api_data: Dict[str, Any]) -> List[str]:
        position_raw = (
            api_data.get("brocardi_info", {}).get("position")
            or api_data.get("position")
            or ""
        )
        if not position_raw:
            return []
        segments = [
            segment.strip()
            for segment in position_raw.split(">")
            if segment.strip()
        ]
        return segments

    def _build_position_classification(
        self,
        position_path: List[str],
        norma_label: str,
        provenance: Provenance,
    ) -> Optional[ExtractionResult]:
        if not position_path:
            return None

        entities: List[ExtractedEntity] = []
        relationships: List[ExtractedRelationship] = []
        parent_label: Optional[str] = None

        for idx, segment in enumerate(position_path):
            # Skip the last element if it's the article itself (e.g., "Articolo 1414")
            # The article node is already created by the main pipeline with label "Codice Civile, art. 1414"
            is_last = idx == len(position_path) - 1
            is_article_node = is_last and segment.lower().startswith("articolo")
            
            if is_article_node:
                # Don't create a duplicate node for the article itself
                # Instead, connect the norma_label directly to the parent structural node
                if parent_label:
                    relationships.append(
                        ExtractedRelationship(
                            source_label=norma_label,
                            target_label=parent_label,
                            type=RelationType.PARTE_DI,
                            properties={
                                "tipo_relazione": "articolo_in_struttura",
                                "fonte": "brocardi_position"
                            },
                            confidence=0.95,
                            provenance=provenance,
                        )
                    )
                continue
            
            # Create structural nodes (Codice, Libro, Titolo, Capo, etc.)
            node_label = segment
            entity = ExtractedEntity(
                type=NodeType.NORMA,
                label=node_label,
                properties={
                    "estremi": segment,
                    "tipo_norma": "strutturale",
                    "livello_gerarchia": idx,
                    "fonte": "brocardi_position",
                },
                confidence=0.99,
                provenance=provenance,
            )
            entities.append(entity)

            # Create hierarchical relationship: child -[parte_di]-> parent
            if parent_label:
                relationships.append(
                    ExtractedRelationship(
                        source_label=node_label,
                        target_label=parent_label,
                        type=RelationType.PARTE_DI,
                        properties={
                            "tipo_relazione": "gerarchia_strutturale",
                            "fonte": "brocardi_position"
                        },
                        confidence=0.95,
                        provenance=provenance,
                    )
                )
            parent_label = node_label

        classification_segment = DocumentSegment(
            text=" > ".join(position_path),
            provenance=provenance,
            metadata={"stage_label": "Fase 1.5 - Classificazione Position"},
        )

        return ExtractionResult(
            segment=classification_segment,
            entities=entities,
            relationships=relationships,
            llm_model="position-derived",
            cost_usd=0.0,
            duration_seconds=0.0,
            tokens_input=0,
            tokens_output=0,
        )

    def _extract_keywords_from_response(self, raw_response: str) -> List[str]:
        """
        Parse keywords list from LLM response.
        
        Expects a JSON array of strings, possibly wrapped in markdown code blocks.
        
        Args:
            raw_response: Raw LLM output
            
        Returns:
            List of concept keyword strings
        """
        try:
            # Try to parse as JSON array directly
            data = json.loads(raw_response)
            if isinstance(data, list):
                return [str(k).strip() for k in data if k and str(k).strip()]
            return []
        except json.JSONDecodeError:
            # Fallback: extract from markdown code block
            if "```json" in raw_response:
                try:
                    json_str = raw_response.split("```json")[1].split("```")[0].strip()
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        return [str(k).strip() for k in data if k and str(k).strip()]
                except (IndexError, json.JSONDecodeError) as e:
                    self.logger.warning(f"Failed to extract keywords from markdown block: {e}")
            
            # Last resort: try raw_decode for partial JSON
            try:
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(raw_response)
                if isinstance(data, list):
                    return [str(k).strip() for k in data if k and str(k).strip()]
            except (json.JSONDecodeError, ValueError):
                pass
            
            self.logger.warning("Could not parse keywords from LLM response, returning empty list")
            return []
