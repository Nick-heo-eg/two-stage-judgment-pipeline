# Two-Stage Judgment Pipeline

⚠️ **Archived Repository**

This repository is archived and no longer actively maintained.

It is preserved as an experimental or evidentiary reference.

It is not part of the current active specification layer.

**For the conceptual entry point of the execution-boundary ecosystem:**
→ [https://github.com/Nick-heo-eg/execution-boundary](https://github.com/Nick-heo-eg/execution-boundary)

---

## Project Status

This repository contains an **early experimental prototype** used to explore whether judgment can be separated from language models.

The experiment successfully demonstrated the concept, but this repository is **no longer maintained or intended for reuse**.

### If you came here from the "6-finger test" discussion

You likely read an earlier experiment exploring whether **judgment happens inside the model or outside it**.

That experiment demonstrated *why test framing matters*, not which model is "better". The original code and logs are preserved as historical evidence, but the work has since shifted toward documenting **how execution and permission should be structured**.

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
Input → Single LLM → Decision + Explanation (coupled)
```

Two-stage approach:
```
Input → Observation → Decision LLM → Explanation LLM
             ↓             ↓              ↓
        (structured)  (binary)     (justification)
```

---

## Architecture

### Stage 1: Observation (External Grounding)

- **Tool**: OpenCV (image processing)
- **Purpose**: Extract objective facts
- **Output**: Structured data (finger count, confidence)

### Stage 2: Decision (Lightweight LLM)

- **Model**: phi3
- **Input**: Structured observation from Stage 1
- **Output**: Binary decision (ALLOW / STOP)

### Stage 3: Explanation (Reasoning LLM)

- **Model**: Mistral-7B
- **Input**: Decision + Observation
- **Output**: Human-readable justification

---

## Why This Matters

**Separation of Concerns:**

- Observation ≠ Decision ≠ Explanation
- Each stage can fail independently
- Each stage can be audited separately

**Testability:**

- Stage 1 output can be validated against ground truth
- Stage 2 logic can be tested with mock observations
- Stage 3 can be evaluated for coherence without affecting decisions

---

## Experimental Results

See `logs/` for full execution traces showing:

- Input images
- Extracted observation data
- Decision outputs
- Explanation justifications

---

## Why This Repository Is Archived

This experiment successfully validated the concept of multi-stage judgment separation.

However, the architecture revealed structural limitations:

1. **External observation dependency** — Requires domain-specific tools (OpenCV for vision, etc.)
2. **Complexity for simple use cases** — Three-stage pipeline is overkill for most scenarios
3. **Shifted focus** — Work has moved toward more general structural definitions

The learnings from this experiment informed later work on execution boundaries and judgment separation.

---

## Historical Context

This repository was created to test:

> "Can judgment be structurally separated from language models?"

**Answer:** Yes, but the separation must be architectural, not just prompt-based.

The code and logs are preserved as evidence of this exploration.

---

## License

MIT License
