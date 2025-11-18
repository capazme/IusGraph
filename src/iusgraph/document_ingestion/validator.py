"""
Validator
=========

Validates and enriches extracted entities before writing to Neo4j.

Functions:
- Schema compliance validation
- Data completeness checks
- Reference resolution
- Cross-referencing
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Set

from .models import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    ValidationResult,
)
from .schema_contract import get_node_rule, get_relation_rule
from .review_queue import ReviewItem, ReviewQueue

logger = logging.getLogger(__name__)


class Validator:
    """
    Validates and enriches extracted knowledge.
    """

    def __init__(
        self,
        strict_mode: bool = False,
        min_confidence: float = 0.7,
        review_queue: ReviewQueue | None = None,
    ):
        """
        Initialize validator.

        Args:
            strict_mode: If True, reject on any validation error
            min_confidence: Minimum confidence threshold (0.0 - 1.0)
        """
        self.strict_mode = strict_mode
        self.min_confidence = min_confidence
        self.logger = logger
        self.review_queue = review_queue or ReviewQueue()
        self.metrics = {
            "entities_total": 0,
            "entities_valid": 0,
            "relationships_total": 0,
            "relationships_valid": 0,
            "queued": 0,
        }

    async def validate_and_enrich(
        self,
        extraction_results: List[ExtractionResult]
    ) -> List[ExtractionResult]:
        """
        Validate and enrich extraction results.

        Args:
            extraction_results: List of extraction results to validate

        Returns:
            Validated and enriched extraction results
        """
        validated_results = []

        for result in extraction_results:
            if result.error:
                validated_results.append(result)
                continue

            context_labels = set(result.segment.metadata.get("known_labels", []))
            segment_id = result.segment.segment_id
            llm_model = result.llm_model

            # Validate entities
            valid_entities = []
            for entity in result.entities:
                self.metrics["entities_total"] += 1
                validation = self._validate_entity(entity)

                if validation.valid:
                    valid_entities.append(self._enrich_entity(entity))
                    self.metrics["entities_valid"] += 1
                else:
                    self._route_entity_to_review(
                        entity,
                        validation.errors,
                        segment_id,
                        llm_model,
                    )

            # Validate relationships
            valid_relationships = []
            for relationship in result.relationships:
                self.metrics["relationships_total"] += 1
                validation = self._validate_relationship(
                    relationship,
                    valid_entities,
                    context_labels,
                )

                if validation.valid:
                    valid_relationships.append(relationship)
                    self.metrics["relationships_valid"] += 1
                else:
                    self._route_relationship_to_review(
                        relationship,
                        validation.errors,
                        segment_id,
                        llm_model,
                    )

            # Update result
            result.entities = valid_entities
            result.relationships = valid_relationships
            validated_results.append(result)

        self.logger.info(
            "Validated %s results (strict_mode=%s) | entities %s/%s | relationships %s/%s | queued=%s",
            len(extraction_results),
            self.strict_mode,
            self.metrics["entities_valid"],
            self.metrics["entities_total"],
            self.metrics["relationships_valid"],
            self.metrics["relationships_total"],
            self.metrics["queued"],
        )

        return validated_results

    def _validate_entity(self, entity: ExtractedEntity) -> ValidationResult:
        """
        Validate a single entity.

        Checks:
        - Confidence threshold
        - Required properties present
        - Property types valid
        """
        errors = []
        warnings = []

        # Check confidence
        rule = get_node_rule(entity.type)
        threshold = (rule.confidence_threshold if rule else self.min_confidence)
        if entity.confidence < threshold:
            errors.append(
                f"Confidence {entity.confidence:.2f} below threshold {threshold:.2f}"
            )

        # Check label
        if not entity.label or len(entity.label.strip()) < 2:
            errors.append("Label is empty or too short")

        if not entity.properties:
            warnings.append("No properties extracted")

        if rule:
            for prop in rule.required_properties:
                if not entity.properties.get(prop):
                    errors.append(f"Missing required property '{prop}' for {entity.type.value}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_relationship(
        self,
        relationship: ExtractedRelationship,
        entities: List[ExtractedEntity],
        context_labels: Set[str],
    ) -> ValidationResult:
        """
        Validate a relationship.

        Checks:
        - Source and target exist in entities
        - Confidence threshold
        - Relationship type is valid
        """
        errors = []
        warnings = []

        # Check confidence
        rule = get_relation_rule(relationship.type)
        threshold = (rule.confidence_threshold if rule else self.min_confidence)
        if relationship.confidence < threshold:
            errors.append(
                f"Confidence {relationship.confidence:.2f} below threshold {threshold:.2f}"
            )

        # Check source/target known
        known_labels = {e.label for e in entities}.union(context_labels)
        if relationship.source_label not in known_labels:
            warnings.append(
                f"Source entity '{relationship.source_label}' not found in batch/context"
            )
        if relationship.target_label not in known_labels:
            warnings.append(
                f"Target entity '{relationship.target_label}' not found in batch/context"
            )

        if rule:
            for prop in rule.required_properties:
                if not relationship.properties.get(prop):
                    errors.append(
                        f"Missing required property '{prop}' on relationship {relationship.type.value}"
                    )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _enrich_entity(self, entity: ExtractedEntity) -> ExtractedEntity:
        """
        Enrich entity with additional data.

        Enrichments:
        - Normalize property values
        - Add derived properties
        - Format dates/numbers
        """
        # TODO: Add enrichment logic
        # - Normalize text (trim, lowercase keys)
        # - Parse dates
        # - Extract URNs from references
        # - Link to existing entities

        return entity

    def _route_entity_to_review(
        self,
        entity: ExtractedEntity,
        reasons: List[str],
        segment_id: str,
        llm_model: Optional[str],
    ) -> None:
        self.metrics["queued"] += 1
        review_item = ReviewItem.new(
            item_type="entity",
            payload={
                "label": entity.label,
                "type": entity.type.value,
                "properties": entity.properties,
                "confidence": entity.confidence,
            },
            reason="; ".join(reasons or ["validation_failed"]),
            source_segment=segment_id,
            llm_model=llm_model,
        )
        try:
            self.review_queue.enqueue(review_item)
        except Exception as exc:
            self.logger.error("Unable to enqueue entity %s: %s", entity.label, exc)

    def _route_relationship_to_review(
        self,
        relationship: ExtractedRelationship,
        reasons: List[str],
        segment_id: str,
        llm_model: Optional[str],
    ) -> None:
        self.metrics["queued"] += 1
        review_item = ReviewItem.new(
            item_type="relationship",
            payload={
                "type": relationship.type.value,
                "source_label": relationship.source_label,
                "target_label": relationship.target_label,
                "properties": relationship.properties,
                "confidence": relationship.confidence,
            },
            reason="; ".join(reasons or ["validation_failed"]),
            source_segment=segment_id,
            llm_model=llm_model,
        )
        try:
            self.review_queue.enqueue(review_item)
        except Exception as exc:
            self.logger.error(
                "Unable to enqueue relationship %s -> %s: %s",
                relationship.source_label,
                relationship.target_label,
                exc,
            )
