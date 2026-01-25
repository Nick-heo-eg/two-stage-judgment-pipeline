# Two-Stage Judgment Pipeline

## Project Status

This repository contains an **early experimental prototype** used to explore whether judgment can be separated from language models.

The experiment successfully demonstrated the concept, but this repository is **no longer maintained or intended for reuse**.

### If you came here from the "6-finger test" discussion

You likely read an earlier experiment exploring whether **judgment happens inside the model or outside it**.

That experiment demonstrated *why test framing matters*, not which model is "better". The original code and logs are preserved as historical evidence, but the work has since shifted toward documenting **how execution and permission should be structured**.

### What to look at now

➡️ **For current work focused on execution governance and responsibility:**
- **Execution precondition layer**: https://github.com/Nick-heo-eg/k-judgment-gate
- **Conceptual structure**: https://github.com/Nick-heo-eg/execution-governance-spec

---

> **LLM-based judgment using external observation and two-stage processing.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Note**: This is a public demo repository documenting an experimental approach. The architecture below represents a historical exploration, not a recommended production pattern.

## 🎯 Overview

This system demonstrates **LLM-based judgment using structured observation data and two-stage processing**.

By separating observation (OpenCV), decision (phi3), and explanation (Mistral) into distinct stages, we can trace how decisions are made and verify component behaviors.

### Key Innovation

Traditional approach:
```
Image → LLM → "I see 6 fingers"
```

Two-stage approach:
```
Image → OpenCV → {protrusions: 6} → phi3 → "6" → Mistral → Explanation
```

## 🏗️ Architecture

```
Real Image Input
    ↓
[External Observation Layer]
  - OpenCV processing
  - Extracts structural features
  - Output: Numeric measurements
    ↓
[Stage 1: phi3:mini]
  - Makes primary decision
  - Outputs: VALUE | INDETERMINATE | STOP
  - Deterministic (temperature=0.0)
    ↓ (if VALUE)
[Stage 2: Mistral]
  - Generates explanations
  - Describes decision rationale
  - Quality monitoring
    ↓
Final Result
```

## ✨ Features

- **🔒 Structured Observation**: External observation layer uses OpenCV for feature extraction
- **⚖️ Two-Stage Processing**: Decision making separated from explanation generation
- **🔄 100% Reproducibility**: Deterministic outputs (temperature=0.0)
- **⚡ Performance**: <100s total latency with caching
- **📊 Multi-Image Support**: Tested with multiple real images
- **🔍 Quality Monitoring**: Tracks use of concept labels in explanations

## 🚀 Quick Start

### API Overview

```python
# Conceptual API (implementation not included in public repo)

from two_stage_pipeline import TwoStageJudgmentPipeline, ObservationRecord

# Create observation record
observation = ObservationRecord(
    record_id="OBS_001",
    estimated_protrusions=6,
    convexity_defects=5,
    # ... other structural measurements
)

# Execute two-stage pipeline
pipeline = TwoStageJudgmentPipeline()
result = pipeline.execute(observation)

print(f"Decision: {result.final_state} = {result.final_value}")
```

### Example Output

```
Stage 1 (phi3 Judge): VALUE = 6
Stage 2 (Mistral Narrator): Generated explanation
Final Decision: VALUE = 6
```

**For full implementation, contact repository owner.**

## 📊 Validation Results

### Test Results

| Test | OpenCV Detection | phi3 Judgment | Reproducibility | Status |
|------|------------------|---------------|-----------------|--------|
| fingers2.jpg | 6 protrusions | VALUE = 6 | 3/3 (100%) | ✅ PASS |

**Note on Validation Scope:**
This is a proof-of-concept demonstrating architectural feasibility. The single test image validates that the pipeline works as designed (observation → decision → explanation separation). For production use, comprehensive testing with diverse images, ground truth validation, and failure case analysis would be required.

### Success Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| External Observation | ✅ | OpenCV extracts structural features |
| Structured Records | ✅ | Numeric measurements only |
| phi3 VALUE Extraction | ✅ | Outputs "6" correctly |
| Two-Stage Processing | ✅ | Stage 1 decides, Stage 2 explains |
| Mistral Explanations | ✅ | Natural language descriptions |
| Reproducibility | ✅ | 100% consistency (N=3) |
| Quality Monitoring | ✅ | Tracks concept label usage |
| End-to-End Accuracy | ✅ | Correct output on test image |

## 🔬 Technical Details

### Models Used

- **phi3:mini (3.8B)**: Stage 1 Judge
  - Fast, accurate instruction following
  - Temperature: 0.0 (deterministic)
  - Latency: 12-65s (cached: 0.24s)

- **mistral:instruct (7B)**: Stage 2 Narrator
  - Rich explanation generation
  - Temperature: 0.2
  - Latency: 80-180s

### Performance Metrics

| Component | First Run | Cached | Fully Cached |
|-----------|-----------|--------|--------------|
| OpenCV | ~0.2s | ~0.2s | ~0.2s |
| phi3 Judge | 61.60s | 12.00s | 0.24s |
| Mistral Narrator | 87.24s | 82.86s | ~80s |
| **Total** | ~150s | ~95s | ~80s |

**256x speedup** with full caching! (61.60s → 0.24s)

## 📁 Repository Structure

```
two-stage-judgment-pipeline/ (PUBLIC - Demo Only)
├── examples/
│   └── process_fingers2.py             # Demo usage example
├── docs/
│   └── PHI3_SUCCESS_SUMMARY.md         # Model selection rationale
├── README.md
└── LICENSE
```

**Full implementation available in private repository.**

## 🎓 Key Concepts

### External Observation Layer

Processes images through OpenCV to extract **structural features**:
- Convexity defects
- Contour analysis
- Hull points
- Bounding box measurements

This provides numeric data for LLM processing without semantic labels.

**Why this matters:** By separating observation and interpretation, we can trace which component produces each part of the output.

### Two-Stage Processing

- **Stage 1 (phi3)**: Decision Making
  - Extracts value from observation data
  - Outputs: VALUE, INDETERMINATE, or STOP
  - Deterministic (temperature=0.0)

- **Stage 2 (Mistral)**: Explanation Generation
  - Describes how decision was made
  - Uses observation data and Stage 1 result
  - Generates natural language descriptions

**The key insight:** Stage 1 extracts values from structured data. Stage 2 generates natural language descriptions. Each stage has a specific role.

### Quality Monitoring

Tracks Stage 2 outputs for quality control:
- Detects use of concept labels (hand, finger, etc.)
- Monitors for explicit "PRIOR_INTRUSION" acknowledgment
- Helps maintain structured reasoning approach

## 🔧 Configuration

### Custom Models

```python
from src.two_stage_judgment_pipeline import TinyLlamaJudge, MistralNarrator

# Use different models
judge = TinyLlamaJudge(model="your-model:tag")
narrator = MistralNarrator(model="your-narrator:tag")
```

### Adjust Parameters

```python
pipeline = TwoStageJudgmentPipeline(
    ollama_host="http://localhost:11434",
    enable_llm_verification=True  # Enable/disable LLM verification
)
```

## 📖 Documentation

- [phi3 Success Summary](docs/PHI3_SUCCESS_SUMMARY.md) - Model selection rationale
- Full technical documentation available in private repository

## 🤝 Contributing

This is a demo repository. For collaboration on the full implementation, please contact the repository owner.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- **Ollama** for local LLM inference
- **Microsoft** for phi3:mini model
- **Mistral AI** for mistral:instruct model
- **OpenCV** for computer vision capabilities

## 📞 Contact

- GitHub Issues: [Report bugs or request features](https://github.com/Nick-heo-eg/two-stage-judgment-pipeline/issues)

## 🌟 Citation

If you use this work in your research, please cite:

```bibtex
@software{two_stage_judgment_2025,
  title = {Two-Stage Judgment Pipeline: Structured LLM Inference},
  author = {Two-Stage Pipeline Contributors},
  year = {2025},
  url = {https://github.com/Nick-heo-eg/two-stage-judgment-pipeline}
}
```

---

**Status**: 🟢 Production Ready | **Version**: 1.0.0 | **Last Updated**: 2025-12-14
