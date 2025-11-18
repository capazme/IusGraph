"""
Experiment Logger for IusGraph Pipeline Runs

Logs every pipeline execution as a structured experiment with:
- Configuration parameters
- Input data
- LLM interactions (prompts, responses, costs)
- Extracted entities and relationships
- Performance metrics
- Errors and warnings

All data is saved in JSON format for scientific analysis and comparison.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class LLMInteraction:
    """Single LLM call within a pipeline step"""
    step_name: str
    model: str
    prompt: str
    raw_response: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    duration_seconds: float
    timestamp: str
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineStep:
    """Single step in the pipeline execution"""
    step_id: str
    step_name: str
    start_time: str
    end_time: str
    duration_seconds: float
    llm_interactions: List[LLMInteraction] = field(default_factory=list)
    entities_extracted: int = 0
    relationships_extracted: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['llm_interactions'] = [interaction.to_dict() for interaction in self.llm_interactions]
        return data


@dataclass
class ExperimentRun:
    """Complete experiment run documentation"""
    # Experiment metadata
    experiment_id: str
    run_timestamp: str
    pipeline_type: str  # "normative" or "interpretive"
    
    # Input configuration
    input_data: Dict[str, Any]
    models_config: Dict[str, str]
    prompts_config: Dict[str, str]
    parameters: Dict[str, Any]
    
    # Execution data
    steps: List[PipelineStep] = field(default_factory=list)
    
    # Output summary
    total_duration_seconds: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    # Status
    status: str = "running"  # "running", "completed", "failed"
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['steps'] = [step.to_dict() for step in self.steps]
        return data
    
    def finalize(self):
        """Calculate final statistics"""
        self.total_duration_seconds = sum(step.duration_seconds for step in self.steps)
        
        for step in self.steps:
            for interaction in step.llm_interactions:
                self.total_cost_usd += interaction.cost_usd
                self.total_tokens_input += interaction.tokens_input
                self.total_tokens_output += interaction.tokens_output
            
            self.total_entities += step.entities_extracted
            self.total_relationships += step.relationships_extracted
        
        if self.error_message:
            self.status = "failed"
        else:
            self.status = "completed"


class ExperimentLogger:
    """
    Manages experiment logging with structured data storage.
    
    Directory structure:
    experiments/
    ├── normative/
    │   ├── 2025-01-18_14-30-45_art1414/
    │   │   ├── experiment.json          # Full experiment data
    │   │   ├── config.json               # Configuration only
    │   │   ├── llm_interactions.jsonl    # Line-delimited LLM calls
    │   │   ├── entities.json             # Extracted entities
    │   │   ├── relationships.json        # Extracted relationships
    │   │   └── summary.md                # Human-readable summary
    │   └── index.json                    # Index of all experiments
    └── interpretive/
        └── ...
    """
    
    def __init__(self, base_dir: str = "experiments"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
    def create_experiment(
        self,
        pipeline_type: str,
        input_data: Dict[str, Any],
        models_config: Dict[str, str],
        prompts_config: Dict[str, str],
        parameters: Dict[str, Any],
    ) -> ExperimentRun:
        """
        Create a new experiment run.
        
        Args:
            pipeline_type: "normative" or "interpretive"
            input_data: Input data for the pipeline (article_id, files, etc.)
            models_config: LLM models used for each step
            prompts_config: Prompts used for each step
            parameters: Additional parameters (batch_size, etc.)
        
        Returns:
            ExperimentRun object
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        
        # Generate experiment ID
        input_hash = hashlib.md5(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()[:8]
        experiment_id = f"{timestamp_str}_{input_hash}"
        
        # Create experiment run
        experiment = ExperimentRun(
            experiment_id=experiment_id,
            run_timestamp=timestamp.isoformat(),
            pipeline_type=pipeline_type,
            input_data=input_data,
            models_config=models_config,
            prompts_config=prompts_config,
            parameters=parameters,
        )
        
        return experiment
    
    def save_experiment(self, experiment: ExperimentRun):
        """
        Save experiment to disk with structured files.
        
        Creates:
        - experiment.json: Complete experiment data
        - config.json: Configuration only (for quick comparison)
        - llm_interactions.jsonl: All LLM calls (for analysis)
        - entities.json: All extracted entities
        - relationships.json: All extracted relationships
        - summary.md: Human-readable summary
        """
        # Finalize statistics
        experiment.finalize()
        
        # Create experiment directory
        exp_dir = self.base_dir / experiment.pipeline_type / experiment.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save complete experiment
        with open(exp_dir / "experiment.json", "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Save configuration only (for quick comparison)
        config = {
            "experiment_id": experiment.experiment_id,
            "timestamp": experiment.run_timestamp,
            "input_data": experiment.input_data,
            "models_config": experiment.models_config,
            "parameters": experiment.parameters,
            "status": experiment.status,
            "summary": {
                "duration_seconds": experiment.total_duration_seconds,
                "cost_usd": experiment.total_cost_usd,
                "entities": experiment.total_entities,
                "relationships": experiment.total_relationships,
            }
        }
        with open(exp_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        # Save LLM interactions (line-delimited JSON for streaming analysis)
        with open(exp_dir / "llm_interactions.jsonl", "w", encoding="utf-8") as f:
            for step in experiment.steps:
                for interaction in step.llm_interactions:
                    f.write(json.dumps(interaction.to_dict(), ensure_ascii=False) + "\n")
        
        # Save summary as markdown
        self._save_summary_markdown(experiment, exp_dir / "summary.md")
        
        # Update index
        self._update_index(experiment)
        
        logger.info(f"Experiment saved: {exp_dir}")
    
    def _save_summary_markdown(self, experiment: ExperimentRun, path: Path):
        """Generate human-readable markdown summary"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Experiment: {experiment.experiment_id}\n\n")
            f.write(f"**Type:** {experiment.pipeline_type}\n")
            f.write(f"**Timestamp:** {experiment.run_timestamp}\n")
            f.write(f"**Status:** {experiment.status}\n\n")
            
            f.write("## Configuration\n\n")
            f.write("### Input Data\n")
            f.write(f"```json\n{json.dumps(experiment.input_data, indent=2)}\n```\n\n")
            
            f.write("### Models\n")
            for step, model in experiment.models_config.items():
                f.write(f"- **{step}**: `{model}`\n")
            f.write("\n")
            
            f.write("### Parameters\n")
            for param, value in experiment.parameters.items():
                f.write(f"- **{param}**: `{value}`\n")
            f.write("\n")
            
            f.write("## Results\n\n")
            f.write(f"- **Duration**: {experiment.total_duration_seconds:.2f}s\n")
            f.write(f"- **Cost**: ${experiment.total_cost_usd:.4f}\n")
            f.write(f"- **Tokens In**: {experiment.total_tokens_input:,}\n")
            f.write(f"- **Tokens Out**: {experiment.total_tokens_output:,}\n")
            f.write(f"- **Entities**: {experiment.total_entities}\n")
            f.write(f"- **Relationships**: {experiment.total_relationships}\n\n")
            
            f.write("## Pipeline Steps\n\n")
            for step in experiment.steps:
                f.write(f"### {step.step_name}\n")
                f.write(f"- Duration: {step.duration_seconds:.2f}s\n")
                f.write(f"- LLM Calls: {len(step.llm_interactions)}\n")
                f.write(f"- Entities: {step.entities_extracted}\n")
                f.write(f"- Relationships: {step.relationships_extracted}\n")
                
                if step.errors:
                    f.write(f"- **Errors**: {len(step.errors)}\n")
                    for error in step.errors:
                        f.write(f"  - {error}\n")
                
                if step.warnings:
                    f.write(f"- **Warnings**: {len(step.warnings)}\n")
                
                f.write("\n")
            
            if experiment.error_message:
                f.write(f"## Error\n\n```\n{experiment.error_message}\n```\n")
    
    def _update_index(self, experiment: ExperimentRun):
        """Update index file with experiment metadata"""
        index_path = self.base_dir / experiment.pipeline_type / "index.json"
        
        # Load existing index
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {"experiments": []}
        
        # Add experiment to index
        index["experiments"].append({
            "experiment_id": experiment.experiment_id,
            "timestamp": experiment.run_timestamp,
            "status": experiment.status,
            "input_data": experiment.input_data,
            "duration_seconds": experiment.total_duration_seconds,
            "cost_usd": experiment.total_cost_usd,
            "entities": experiment.total_entities,
            "relationships": experiment.total_relationships,
        })
        
        # Sort by timestamp (newest first)
        index["experiments"].sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Save index
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    
    def load_experiment(self, pipeline_type: str, experiment_id: str) -> ExperimentRun:
        """Load an experiment from disk"""
        exp_path = self.base_dir / pipeline_type / experiment_id / "experiment.json"
        
        if not exp_path.exists():
            raise FileNotFoundError(f"Experiment not found: {experiment_id}")
        
        with open(exp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Reconstruct ExperimentRun (simplified, you may need to reconstruct nested objects)
        return data
    
    def list_experiments(self, pipeline_type: str) -> List[Dict[str, Any]]:
        """List all experiments for a pipeline type"""
        index_path = self.base_dir / pipeline_type / "index.json"
        
        if not index_path.exists():
            return []
        
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        return index["experiments"]
    
    def compare_experiments(
        self,
        pipeline_type: str,
        experiment_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Compare multiple experiments.
        
        Returns a comparison table with key metrics.
        """
        experiments = []
        for exp_id in experiment_ids:
            exp_data = self.load_experiment(pipeline_type, exp_id)
            experiments.append(exp_data)
        
        comparison = {
            "experiments": experiment_ids,
            "metrics": {
                "duration_seconds": [exp["total_duration_seconds"] for exp in experiments],
                "cost_usd": [exp["total_cost_usd"] for exp in experiments],
                "entities": [exp["total_entities"] for exp in experiments],
                "relationships": [exp["total_relationships"] for exp in experiments],
            }
        }
        
        return comparison

