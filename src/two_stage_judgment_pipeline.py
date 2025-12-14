#!/usr/bin/env python3
"""
Two-Stage Judgment Pipeline: phi3 (Judge) + Mistral (Narrator)

Architecture:
- Stage 1: Primary decision using phi3:mini (outputs VALUE/INDETERMINATE/STOP)
- Stage 2: Explanation generation using Mistral (describes Stage 1 decision)

Design:
- Stage 1 makes the final decision
- Stage 2 generates explanations based on observation data
- Both stages use structured observation records (no concept labels)
"""

import json
import logging
import requests
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Tuple, Dict, Any
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# Judgment states
JudgmentState = Literal["VALUE", "INDETERMINATE", "STOP"]


@dataclass
class ObservationRecord:
    """Observation record (concept-free)"""
    record_id: str
    timestamp: str
    estimated_protrusions: int
    convexity_defects: int
    contour_area: float
    hull_points: int
    bbox_width: int
    bbox_height: int
    aspect_ratio: float
    image_path: str
    processing_method: str


@dataclass
class Stage1JudgmentResult:
    """Stage 1: TinyLlama judgment result"""
    record_id: str
    timestamp: str

    # Judgment
    state: JudgmentState  # VALUE, INDETERMINATE, STOP
    value: Optional[int]  # Only valid when state == VALUE

    # Raw outputs
    raw_response: str

    # Metadata
    model: str
    latency_s: float
    reasoning_trace: str


@dataclass
class Stage2NarrativeResult:
    """Stage 2: Mistral narrative result"""
    record_id: str
    timestamp: str

    # Stage 1 result (read-only)
    stage1_state: JudgmentState
    stage1_value: Optional[int]

    # Narrative (explanation)
    explanation: str

    # Prior intrusion detection
    prior_intrusion_detected: bool
    intrusion_evidence: str

    # Raw outputs
    raw_response: str

    # Metadata
    model: str
    latency_s: float


@dataclass
class TwoStagePipelineResult:
    """Complete pipeline result"""
    record_id: str
    timestamp: str

    # Stage 1 (judgment)
    stage1_result: Stage1JudgmentResult

    # Stage 2 (narrative) - None if STOP/INDETERMINATE
    stage2_result: Optional[Stage2NarrativeResult]

    # Final decision (always from Stage 1 judgment)
    final_state: JudgmentState
    final_value: Optional[int]

    # Quality signals
    pipeline_stopped_early: bool
    prior_intrusion_detected: bool


class TinyLlamaJudge:
    """Stage 1: Lightweight LLM judge (VALUE/INDETERMINATE/STOP)"""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "phi3:mini",  # phi3:mini > tinyllama for instruction following
    ):
        self.ollama_host = ollama_host
        self.model = model

    def judge(self, observation: ObservationRecord) -> Stage1JudgmentResult:
        """
        Primary judgment: Observation Record → VALUE/INDETERMINATE/STOP

        Outputs:
        - VALUE: Valid numeric result extracted
        - INDETERMINATE: Insufficient data or parsing failure
        - STOP: Unable to trace evidence source
        """
        logger.info("=" * 80)
        logger.info("STAGE 1: TINYLLAMA JUDGMENT")
        logger.info("=" * 80)
        logger.info(f"Model: {self.model}")
        logger.info(f"Observation: {observation.record_id}")
        logger.info("")

        start_time = time.time()

        # Serialize observation record
        obs_text = self._serialize_observation(observation)

        # Build judgment prompt
        prompt = self._build_judgment_prompt(obs_text)

        logger.info("Calling TinyLlama for judgment...")
        logger.info("")

        # Call Ollama
        raw_response = self._call_ollama(prompt)

        # Parse response
        state, value, reasoning = self._parse_judgment(raw_response)

        latency = time.time() - start_time

        logger.info(f"State: {state}")
        logger.info(f"Value: {value}")
        logger.info(f"Reasoning: {reasoning}")
        logger.info(f"Latency: {latency:.2f}s")
        logger.info("=" * 80)
        logger.info("")

        return Stage1JudgmentResult(
            record_id=observation.record_id,
            timestamp=datetime.now().isoformat(),
            state=state,
            value=value,
            raw_response=raw_response,
            model=self.model,
            latency_s=round(latency, 2),
            reasoning_trace=reasoning,
        )

    def _serialize_observation(self, observation: ObservationRecord) -> str:
        """Observation record → text (concept-free)"""
        return f"""Observation Record: {observation.record_id}

Structural Measurements (NO concept labels):
- Estimated protrusions: {observation.estimated_protrusions}
- Convexity defects: {observation.convexity_defects}
- Contour area: {observation.contour_area:.0f} px
- Hull points: {observation.hull_points}
- Bounding box: {observation.bbox_width} x {observation.bbox_height}
- Aspect ratio: {observation.aspect_ratio:.2f}

Processing method: {observation.processing_method}"""

    def _build_judgment_prompt(self, obs_text: str) -> str:
        """Build simple extraction prompt optimized for small models"""
        return f"""Read the observation data and output the "estimated_protrusions" value.

{obs_text}

Output ONLY the number.
Answer:"""

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,  # Deterministic
                "num_predict": 10,   # Very short response
                "top_p": 1.0,
            }
        }

        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "ERROR").strip()

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "ERROR"

    def _parse_judgment(self, response: str) -> Tuple[JudgmentState, Optional[int], str]:
        """Parse response: (state, value, reasoning) - flexible extraction"""
        response_clean = response.strip()

        # Check for STOP (in full response)
        if "STOP" in response_clean.upper():
            return "STOP", None, "Evidence source untraceable"

        # Check for INDETERMINATE (in full response)
        if "INDETERMINATE" in response_clean.upper():
            return "INDETERMINATE", None, "Insufficient evidence"

        # Extract VALUE (integer) - find first number in full response
        numbers = re.findall(r'\b\d+\b', response_clean)
        if numbers:
            value = int(numbers[0])
            return "VALUE", value, f"Based on structural observation: {value}"

        # Parse failed → INDETERMINATE
        first_line = response_clean.split("\n")[0][:50]  # First 50 chars only
        return "INDETERMINATE", None, f"Parse failed: {first_line}"


class MistralNarrator:
    """Stage 2: Mistral narrator (explanation only, no judgment authority)"""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "mistral:instruct",
    ):
        self.ollama_host = ollama_host
        self.model = model

    def narrate(
        self,
        observation: ObservationRecord,
        stage1_result: Stage1JudgmentResult,
    ) -> Stage2NarrativeResult:
        """
        Generate explanation for Stage 1 decision.

        Inputs:
        - observation: Structured observation record
        - stage1_result: Primary judgment from Stage 1

        Outputs:
        - explanation: Natural language description
        - quality_check: Detects use of concept labels
        """
        logger.info("=" * 80)
        logger.info("STAGE 2: MISTRAL NARRATIVE")
        logger.info("=" * 80)
        logger.info(f"Model: {self.model}")
        logger.info(f"Stage 1 Result: {stage1_result.state} = {stage1_result.value}")
        logger.info("")

        start_time = time.time()

        # Observation record + Stage 1 result
        context = self._build_narrative_context(observation, stage1_result)

        # Build narrative prompt
        prompt = self._build_narrative_prompt(context)

        logger.info("Calling Mistral for explanation...")
        logger.info("")

        # Call Ollama
        raw_response = self._call_ollama(prompt)

        # Detect prior intrusion
        prior_detected, evidence = self._detect_prior_intrusion(raw_response)

        latency = time.time() - start_time

        logger.info(f"Explanation: {raw_response[:200]}...")
        logger.info(f"Prior Intrusion: {prior_detected}")
        if prior_detected:
            logger.info(f"  Evidence: {evidence}")
        logger.info(f"Latency: {latency:.2f}s")
        logger.info("=" * 80)
        logger.info("")

        return Stage2NarrativeResult(
            record_id=observation.record_id,
            timestamp=datetime.now().isoformat(),
            stage1_state=stage1_result.state,
            stage1_value=stage1_result.value,
            explanation=raw_response,
            prior_intrusion_detected=prior_detected,
            intrusion_evidence=evidence,
            raw_response=raw_response,
            model=self.model,
            latency_s=round(latency, 2),
        )

    def _build_narrative_context(
        self,
        observation: ObservationRecord,
        stage1_result: Stage1JudgmentResult,
    ) -> str:
        """Build narrative context"""
        return f"""OBSERVATION RECORD:
{TinyLlamaJudge(self.ollama_host, "")._serialize_observation(observation)}

STAGE 1 JUDGMENT (PRIMARY JUDGE - TinyLlama):
- State: {stage1_result.state}
- Value: {stage1_result.value}
- Reasoning: {stage1_result.reasoning_trace}"""

    def _build_narrative_prompt(self, context: str) -> str:
        """Build explanation prompt for Stage 2"""
        return f"""You are an explanation generator. Describe how the decision was made based on the observation data.

CONTEXT:
{context}

TASK:
Explain the decision based on the structural measurements provided.
Avoid using concept labels like "hand" or "finger" - stick to structural terms.
If you use common sense, mention "PRIOR_INTRUSION" explicitly.

EXPLANATION:"""

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 200,
            }
        }

        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "ERROR").strip()

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "ERROR"

    def _detect_prior_intrusion(self, response: str) -> Tuple[bool, str]:
        """Detect use of concept labels in explanation"""

        # Check for explicit acknowledgment
        if "PRIOR_INTRUSION" in response.upper():
            return True, "Explicitly acknowledged"

        # Check for concept labels (quality control)
        concept_keywords = ["hand", "finger", "thumb", "palm", "digit"]
        response_lower = response.lower()
        found_concepts = [kw for kw in concept_keywords if kw in response_lower]

        if found_concepts:
            return True, f"Concept labels: {', '.join(found_concepts)}"

        return False, ""


class TwoStageJudgmentPipeline:
    """Two-stage pipeline: phi3 (decision) + Mistral (explanation)"""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.judge = TinyLlamaJudge(ollama_host)
        self.narrator = MistralNarrator(ollama_host)

    def execute(
        self,
        observation: ObservationRecord,
    ) -> TwoStagePipelineResult:
        """
        Execute two-stage pipeline

        Flow:
        1. Stage 1 (phi3): Make decision
        2. If STOP/INDETERMINATE → Early termination
        3. If VALUE → Stage 2 (Mistral): Generate explanation
        """
        logger.info("\n")
        logger.info("╔" + "=" * 78 + "╗")
        logger.info("║" + " " * 20 + "TWO-STAGE JUDGMENT PIPELINE" + " " * 30 + "║")
        logger.info("╚" + "=" * 78 + "╝")
        logger.info("\n")

        # Stage 1: TinyLlama judgment
        stage1_result = self.judge.judge(observation)

        # Early termination check
        if stage1_result.state in ["STOP", "INDETERMINATE"]:
            logger.info(f"🛑 Pipeline stopped early: {stage1_result.state}")
            logger.info(f"   Reason: {stage1_result.reasoning_trace}")
            logger.info("")

            return TwoStagePipelineResult(
                record_id=observation.record_id,
                timestamp=datetime.now().isoformat(),
                stage1_result=stage1_result,
                stage2_result=None,
                final_state=stage1_result.state,
                final_value=None,
                pipeline_stopped_early=True,
                prior_intrusion_detected=False,
            )

        # Stage 2: Mistral narrative (only for VALUE case)
        logger.info(f"✅ Stage 1 completed: VALUE = {stage1_result.value}")
        logger.info(f"   Proceeding to Stage 2 (Narrative)...")
        logger.info("")

        stage2_result = self.narrator.narrate(observation, stage1_result)

        # Final result
        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Final State: {stage1_result.state}")
        logger.info(f"Final Value: {stage1_result.value}")
        logger.info(f"Prior Intrusion: {stage2_result.prior_intrusion_detected}")
        logger.info("=" * 80)
        logger.info("")

        return TwoStagePipelineResult(
            record_id=observation.record_id,
            timestamp=datetime.now().isoformat(),
            stage1_result=stage1_result,
            stage2_result=stage2_result,
            final_state=stage1_result.state,
            final_value=stage1_result.value,
            pipeline_stopped_early=False,
            prior_intrusion_detected=stage2_result.prior_intrusion_detected,
        )

    def save_result(self, result: TwoStagePipelineResult, filepath: Path):
        """Save result"""
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Result saved: {filepath}")


def test_reproducibility(
    pipeline: TwoStageJudgmentPipeline,
    observation: ObservationRecord,
    n_runs: int = 3,
) -> bool:
    """Reproducibility test: same input → same judgment"""

    logger.info("\n")
    logger.info("=" * 80)
    logger.info("REPRODUCIBILITY TEST")
    logger.info("=" * 80)
    logger.info(f"Running {n_runs} times with same observation...")
    logger.info("")

    results = []

    for i in range(n_runs):
        logger.info(f"Run {i+1}/{n_runs}")
        result = pipeline.execute(observation)
        results.append((result.final_state, result.final_value))
        logger.info(f"  Result: {result.final_state} = {result.final_value}")
        logger.info("")

    # Check if all results are identical
    all_same = len(set(results)) == 1

    logger.info("Results:")
    logger.info(f"  {results}")
    logger.info(f"  All same: {all_same}")

    if all_same:
        logger.info("  ✅ PASS: Reproducible")
    else:
        logger.info("  ❌ FAIL: Not reproducible")

    logger.info("=" * 80)
    logger.info("")

    return all_same


def main():
    """Main execution"""

    # Load observation record from previous run
    obs_file = Path("observation_record_real.json")

    if not obs_file.exists():
        logger.error(f"❌ Observation record not found: {obs_file}")
        logger.error("   Please run real_image_finger_counter.py first")
        return 1

    with obs_file.open("r", encoding="utf-8") as f:
        obs_data = json.load(f)

    observation = ObservationRecord(**obs_data)

    logger.info(f"✅ Loaded observation: {observation.record_id}")
    logger.info(f"   Estimated protrusions: {observation.estimated_protrusions}")
    logger.info("")

    # Create pipeline
    pipeline = TwoStageJudgmentPipeline()

    # Execute
    result = pipeline.execute(observation)

    # Save
    output_file = Path("two_stage_result.json")
    pipeline.save_result(result, output_file)

    # Reproducibility test
    logger.info("Running reproducibility test...")
    reproducible = test_reproducibility(pipeline, observation, n_runs=3)

    # Final summary
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Observation: {observation.record_id}")
    logger.info(f"Estimated Protrusions: {observation.estimated_protrusions}")
    logger.info("")
    logger.info("STAGE 1 (TinyLlama - JUDGE):")
    logger.info(f"  State: {result.final_state}")
    logger.info(f"  Value: {result.final_value}")
    logger.info("")

    if result.stage2_result:
        logger.info("STAGE 2 (Mistral - NARRATOR):")
        logger.info(f"  Explanation: {result.stage2_result.explanation[:100]}...")
        logger.info(f"  Prior Intrusion: {result.prior_intrusion_detected}")
        if result.prior_intrusion_detected:
            logger.info(f"    Evidence: {result.stage2_result.intrusion_evidence}")
    else:
        logger.info("STAGE 2: Skipped (early termination)")

    logger.info("")
    logger.info("Success Criteria:")
    logger.info(f"  ✅ Judgment authority fixed to TinyLlama: YES")
    logger.info(f"  ✅ Mistral performs explanation only: YES")
    logger.info(f"  {'✅' if reproducible else '❌'} Reproducibility: {'PASS' if reproducible else 'FAIL'}")
    logger.info(f"  {'⚠️ ' if result.prior_intrusion_detected else '✅'} Prior intrusion prevented: {'WARNING' if result.prior_intrusion_detected else 'PASS'}")
    logger.info("=" * 80)
    logger.info("")

    return 0 if reproducible else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
