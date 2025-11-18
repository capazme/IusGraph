"""
LLM Extractor
=============

Uses Large Language Models (Claude/GPT-4) via OpenRouter to extract
structured entities and relationships from legal text.

Extracts according to the MERL-T Knowledge Graph schema (23 node types).
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from datetime import datetime

from .models import (
    DocumentSegment,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    NodeType,
    RelationType,
)
from .schema_contract import (
    NODE_TYPE_ALIASES,
    RELATION_TYPE_ALIASES,
    clamp_confidence,
    get_prompt_contract_block,
)

logger = logging.getLogger(__name__)


class LLMExtractor:
    """
    Extracts entities and relationships from legal text using LLMs.
    This class is a stateless tool for calling an LLM with a given prompt.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.5-flash",
        temperature: float = 0.1,
        max_tokens: int = 4000,
        timeout_seconds: int = 60,
        use_structured_outputs: bool = True,
        structured_output_models: Optional[List[str]] = None,
    ):
        """
        Initialize LLM extractor.

        Args:
            api_key: OpenRouter API key
            default_model: Default model to use if not specified per call.
            temperature: Temperature for generation (lower = more consistent)
            max_tokens: Maximum tokens in response
            timeout_seconds: Request timeout
        """
        # Core configuration
        self.api_key = api_key
        self.default_model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.logger = logger
        
        # Structured outputs configuration
        self.use_structured_outputs = use_structured_outputs
        self.response_format = self._build_response_format()
        self.schema_contract_block = get_prompt_contract_block()
        
        # Models that support structured outputs (prefixes for matching)
        self.structured_output_models = structured_output_models or [
            "google/gemini",
            "openai/gpt-4o",
            "openai/gpt-4-turbo",
            "openai/gpt-4",
            "anthropic/claude-3.5",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "deepseek/deepseek-r1",
            "fireworks/",
        ]

        # Pricing per million tokens (input/output)
        self.pricing = {
            "google/gemini-2.5-flash": {"input": 0.3, "output": 0.6},
            "google/gemini-2.5-pro": {"input": 1.25, "output": 10},
            "openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "openai/gpt-4o": {"input": 5.0, "output": 15.0},
            "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
            "deepseek/deepseek-r1": {"input": 0.55, "output": 2.19},
        }

    async def extract_from_segment(
        self,
        segment: DocumentSegment,
        prompt_template: str,
        model_override: Optional[str] = None,
        context_data: Optional[Dict[str, str]] = None,
    ) -> ExtractionResult:
        """
        Extract entities and relationships from a single segment.

        Args:
            segment: Document segment to process.
            prompt_template: The prompt template string to use for this extraction.
            model_override: Optional model name to use instead of the default.
            context_data: Optional dict to fill placeholders in the prompt.

        Returns:
            ExtractionResult with extracted entities/relationships
        """
        start_time = datetime.utcnow()
        model_to_use = model_override or self.default_model

        try:
            prompt = self._build_prompt(prompt_template, segment, context_data)

            # Call LLM
            response = await self._call_llm(prompt, model_to_use)

            # Parse response
            entities, relationships = self._parse_response(
                response["content"],
                segment.provenance,
                prompt,
            )

            # Calculate cost
            tokens_input = response.get("usage", {}).get("prompt_tokens", 0)
            tokens_output = response.get("usage", {}).get("completion_tokens", 0)
            cost = self._calculate_cost(tokens_input, tokens_output, model_to_use)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ExtractionResult(
                segment=segment,
                entities=entities,
                relationships=relationships,
                llm_model=model_to_use,
                cost_usd=cost,
                duration_seconds=duration,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                raw_response=response["content"],
                prompt=prompt,
            )

        except Exception as e:
            self.logger.error(f"Error extracting from segment: {e}", exc_info=True)
            duration = (datetime.utcnow() - start_time).total_seconds()

            return ExtractionResult(
                segment=segment,
                entities=[],
                relationships=[],
                llm_model=model_to_use,
                duration_seconds=duration,
                error=str(e),
                prompt=prompt if "prompt" in locals() else "",
            )

    def _build_prompt(
        self,
        template: str,
        segment: DocumentSegment,
        context_data: Optional[Dict[str, str]],
    ) -> str:
        """Replace placeholders in prompt templates safely."""
        prompt = template
        text_to_analyze = segment.text if segment.text is not None else ""
        prompt = prompt.replace("__TEXT_TO_ANALYZE__", text_to_analyze)

        if context_data:
            for key, value in context_data.items():
                prompt = prompt.replace(f"__{key}__", str(value))

        if "__SCHEMA_CONTRACT__" in prompt:
            prompt = prompt.replace("__SCHEMA_CONTRACT__", self.schema_contract_block)

        return prompt

    async def extract_batch(
        self,
        segments: List[DocumentSegment],
        max_concurrent: int = 3,
        prompt_template_override: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> List[ExtractionResult]:
        """
        Extract over a batch of segments while respecting concurrency limits.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _process(segment: DocumentSegment) -> ExtractionResult:
            prompt_template = (
                prompt_template_override or segment.metadata.get("prompt_template")
            )
            if not prompt_template:
                raise ValueError(
                    f"Missing prompt template for segment {segment.segment_id}"
                )
            prompt_context = segment.metadata.get("prompt_context", {})
            async with semaphore:
                return await self.extract_from_segment(
                    segment=segment,
                    prompt_template=prompt_template,
                    model_override=model_override,
                    context_data=prompt_context,
                )

        tasks = [_process(segment) for segment in segments]
        return await asyncio.gather(*tasks)

    async def _call_llm(self, prompt: str, model: str) -> Dict[str, Any]:
        """
        Call OpenRouter API with prompt.

        Args:
            prompt: The prompt to send
            model: The model to use for this specific call
            
        Returns:
            Dict with 'content' (str) and 'usage' (dict) keys
            
        Raises:
            RuntimeError: If API call fails or returns invalid response
        """
        # Validate inputs
        if not model or not model.strip():
            raise ValueError("Model name cannot be empty")
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        # Apply structured outputs if supported
        supports_structured = self._model_supports_structured(model)
        if self.use_structured_outputs and supports_structured:
            payload["response_format"] = self.response_format
            self.logger.debug("Using structured outputs for model: %s", model)
        elif self.use_structured_outputs and not supports_structured:
            self.logger.info(
                "Structured outputs not available for model: %s (not in supported list)",
                model,
            )

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.api_url, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"OpenRouter API error (status {response.status}): {error_text}"
                        )
                    
                    data = await response.json()
                    
                    # Validate response structure
                    if "choices" not in data or not data["choices"]:
                        raise RuntimeError(f"Invalid API response: missing 'choices'. Response: {data}")
                    
                    if "message" not in data["choices"][0]:
                        raise RuntimeError(f"Invalid API response: missing 'message'. Response: {data}")
                    
                    if "content" not in data["choices"][0]["message"]:
                        raise RuntimeError(f"Invalid API response: missing 'content'. Response: {data}")
                    
                    content = data["choices"][0]["message"]["content"]
                    if content is None:
                        raise RuntimeError(f"API returned null content for model: {model}")
                    
                    return {
                        "content": content,
                        "usage": data.get("usage", {}),
                    }
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error calling OpenRouter API: {e}") from e
        except asyncio.TimeoutError as e:
            raise RuntimeError(f"Timeout calling OpenRouter (>{self.timeout_seconds}s) for model {model}") from e

    def _parse_response(
        self,
        response_text: str,
        provenance,
        prompt_text: str,
    ) -> tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """
        Parse JSON response from LLM, normalizing fields to match enums and schema contract.
        """
        try:
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(json_str.strip())
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse LLM response as JSON: %s | prompt preview: %s | response preview: %s",
                e,
                prompt_text[:500],
                response_text[:500],
            )
            return [], []

        entities: List[ExtractedEntity] = []
        for ent_data in data.get("entities", []):
            normalized = self._normalize_entity(ent_data)
            if not normalized:
                continue
            try:
                entities.append(
                    ExtractedEntity(
                        type=normalized["type"],
                        label=normalized["label"],
                        properties=normalized["properties"],
                        confidence=normalized["confidence"],
                        provenance=provenance,
                    )
                )
            except Exception as exc:
                self.logger.warning(
                    f"Skipping entity {ent_data.get('label')}: {exc}"
                )

        relationships: List[ExtractedRelationship] = []
        for rel_data in data.get("relationships", []):
            normalized = self._normalize_relationship(rel_data)
            if not normalized:
                continue
            try:
                relationships.append(
                    ExtractedRelationship(
                        source_label=normalized["source_label"],
                        target_label=normalized["target_label"],
                        type=normalized["type"],
                        properties=normalized["properties"],
                        confidence=normalized["confidence"],
                        provenance=provenance,
                    )
                )
            except Exception as exc:
                self.logger.warning(
                    f"Skipping relationship {rel_data.get('type')}: {exc}"
                )

        return entities, relationships

    def _normalize_entity(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a raw entity dict from the LLM output."""
        if not isinstance(payload, dict):
            self.logger.warning("Entity payload is not a dict, skipping")
            return None

        raw_type = str(payload.get("type", "")).strip()
        label = str(payload.get("label", "")).strip()

        if not raw_type or not label:
            self.logger.warning("Entity missing required fields 'type' or 'label'")
            return None

        try:
            node_type = self._coerce_node_type(raw_type)
        except ValueError:
            self.logger.warning(f"Unknown entity type '{raw_type}', skipping")
            return None

        properties = payload.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}

        confidence = clamp_confidence(payload.get("confidence"))

        return {
            "type": node_type,
            "label": label,
            "properties": properties,
            "confidence": confidence,
        }

    def _normalize_relationship(
        self,
        payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Normalize a raw relationship dict from the LLM output."""
        if not isinstance(payload, dict):
            self.logger.warning("Relationship payload is not a dict, skipping")
            return None

        raw_type = str(payload.get("type") or payload.get("label") or "").strip()
        if not raw_type:
            self.logger.warning("Relationship missing 'type', skipping")
            return None

        try:
            rel_type = self._coerce_relation_type(raw_type)
        except ValueError:
            self.logger.warning(f"Unknown relationship type '{raw_type}', skipping")
            return None

        source_label = (
            payload.get("source_label")
            or payload.get("source")
            or payload.get("start_label")
            or payload.get("start")
            or payload.get("start_node_label")
            or payload.get("start_node_id")
        )
        target_label = (
            payload.get("target_label")
            or payload.get("target")
            or payload.get("end_label")
            or payload.get("end")
            or payload.get("end_node_label")
            or payload.get("end_node_id")
        )

        if not source_label or not target_label:
            self.logger.warning(
                f"Relationship {rel_type.value} missing source/target labels"
            )
            return None

        properties = payload.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}

        confidence = clamp_confidence(payload.get("confidence"))

        return {
            "type": rel_type,
            "source_label": str(source_label).strip(),
            "target_label": str(target_label).strip(),
            "properties": properties,
            "confidence": confidence,
        }

    def _coerce_node_type(self, raw_type: str) -> NodeType:
        canonical = NODE_TYPE_ALIASES.get(raw_type, raw_type)
        if isinstance(canonical, NodeType):
            return canonical
        return NodeType(canonical)

    def _coerce_relation_type(self, raw_type: str) -> RelationType:
        canonical = RELATION_TYPE_ALIASES.get(raw_type, raw_type.lower())
        if isinstance(canonical, RelationType):
            return canonical
        return RelationType(canonical)

    def _model_supports_structured(self, model: str) -> bool:
        """
        Check if the provided model supports structured outputs.
        
        Args:
            model: Full model identifier (e.g., "google/gemini-2.5-flash", "deepseek/deepseek-r1:free")
            
        Returns:
            True if model is in the supported list (prefix match), False otherwise
        """
        if not model:
            return False
            
        # Normalize model name for comparison (lowercase, handle variants like :free)
        normalized = model.lower().strip()
        
        # Check against known prefixes
        for prefix in self.structured_output_models:
            prefix_normalized = prefix.lower().strip()
            if normalized.startswith(prefix_normalized):
                self.logger.debug(f"Model '{model}' supports structured outputs (matched prefix: '{prefix}')")
                return True
        
        self.logger.debug(f"Model '{model}' does not support structured outputs")
        return False

    def _build_response_format(self) -> Dict[str, Any]:
        """
        JSON schema enforcing the canonical MERL-T extraction envelope.
        """
        entity_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Node type (e.g., Norma)"},
                "label": {"type": "string", "description": "Canonical label"},
                "properties": {
                    "type": "object",
                    "description": "Node properties per schema",
                    "additionalProperties": True,
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0-1",
                },
            },
            "required": ["type", "label", "properties", "confidence"],
            "additionalProperties": False,
        }

        relationship_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Relationship type"},
                "source_label": {
                    "type": "string",
                    "description": "Label of source entity",
                },
                "target_label": {
                    "type": "string",
                    "description": "Label of target entity",
                },
                "properties": {
                    "type": "object",
                    "description": "Relationship properties per schema",
                    "additionalProperties": True,
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0-1",
                },
            },
            "required": ["type", "source_label", "target_label", "properties", "confidence"],
            "additionalProperties": False,
        }

        return {
            "type": "json_schema",
            "json_schema": {
                "name": "merlt_extraction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": entity_schema,
                            "description": "List of nodes to create/update",
                        },
                        "relationships": {
                            "type": "array",
                            "items": relationship_schema,
                            "description": "List of relationships to create",
                        },
                    },
                    "required": ["entities", "relationships"],
                    "additionalProperties": False,
                },
            },
        }

    def _calculate_cost(self, tokens_input: int, tokens_output: int, model: str) -> float:
        """
        Calculate cost in USD for the API call.
        
        Args:
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            model: Model identifier
            
        Returns:
            Estimated cost in USD (0.0 if pricing unknown)
        """
        if model not in self.pricing:
            # Try to find pricing by prefix match
            model_lower = model.lower()
            for known_model, prices in self.pricing.items():
                if model_lower.startswith(known_model.lower().rsplit(":", 1)[0]):
                    pricing = prices
                    break
            else:
                # Unknown model - log warning and return 0
                self.logger.warning(
                    f"No pricing data for model '{model}'. Cost will be 0. "
                    f"Add pricing to LLMExtractor.pricing dict."
                )
                return 0.0
        else:
            pricing = self.pricing[model]
        
        cost_input = (tokens_input / 1_000_000) * pricing["input"]
        cost_output = (tokens_output / 1_000_000) * pricing["output"]
        return cost_input + cost_output
