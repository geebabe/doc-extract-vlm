# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project: OCR API (PaddleOCR + vLLM)

A FastAPI service combining PaddleOCR (text spotting) with Qwen3-VL-2B via vLLM (visual reasoning + schema-constrained generation) for structured data extraction from Vietnamese documents.

### Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run server (development)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest -q

# Run a single test file
pytest tests/test_prompt_builder.py -q

# Docker (full stack: API + vLLM model)
export HF_TOKEN=hf_xxx
docker compose up -d

# Health check
curl http://localhost:8000/health/

# Single-image CLI inference
python inference.py --image data/cccd.jpg --doc-type id_card --draw

# Batch inference over a directory
python batch_inference.py --batch data/invoices/ --doc-type invoice --num-workers 4 --output results.jsonl
```

### Environment Variables (`.env`)

```env
PROJECT_NAME="OCR API"
VLLM_BASE_URL="http://localhost:8001/v1"
VLLM_MODEL_NAME="Qwen/Qwen3-VL-2B-Instruct"
VLLM_API_KEY="none"
OCR_LANG="vi"
OCR_VERSION="PP-OCRv5"
OCR_TEXT_REC_SCORE_THRESH=0.5
# Optional debug: dumps OCR text, prompt, and VLM response to DEBUG_DUMP_DIR per request
DEBUG_DUMP_ENABLED=false
DEBUG_DUMP_DIR="debug_dumps"
```

### Architecture

Two-stage pipeline per request:
1. **PaddleOCR** detects text and bounding boxes (run in thread pool via `asyncio.to_thread`)
2. **Qwen3-VL-2B** (via vLLM) sees image + OCR hints and emits schema-constrained JSON
3. **Post-processor** fuzzy-matches VLM values against OCR text to catch hallucinations

Request flow: `src/api/routes/extract.py` → `src/services/vlm_processor.py` (orchestrates pipeline) → `src/services/prompt_builder.py` (builds system prompt) → vLLM API → `src/services/post_processor.py`

**Concurrency**: A `asyncio.Semaphore(4)` in `extract.py` caps in-flight GPU requests. Keep it `<= --max-num-seqs` configured on vLLM (default 8 in `docker-compose.yml`).

### Key Design Constraints

- **GPU memory sharing**: `ocr_engine.py` sets `FLAGS_fraction_of_gpu_memory_to_use=0.08` *before* importing paddle — don't reorder those imports or PaddleOCR will grab all VRAM.
- **OCR coordinates are normalized to `[0, 1000]`**, not raw pixels. Prompts, post-processing, and inference bbox drawing all assume this scale.
- **Two PaddleOCR output shapes** are handled in `vlm_processor.run_paddle_ocr_normalized`: newer dict form (`rec_texts`/`rec_boxes`) and older list-of-quadrilateral form.
- **CCCD side detection**: `prompt_builder.detect_cccd_side()` inspects OCR text for MRZ lines (`IDVNM`) to auto-select front vs. back field definitions.
- **`response_format=schema_class`** uses OpenAI's parsed-completions API requiring vLLM guided decoding. If `parsed` is null, vLLM can't constrain to that schema.
- **Models warm on startup** in `main.py`'s `startup_event` — a bad `VLLM_BASE_URL` lets the app boot but every request 500s.

### Adding a New Document Type

1. Define Pydantic schema in `src/schemas/<type>.py` using `BBoxField` for every located field
2. Add a `PromptConfig` entry in `PROMPT_CONFIGS` dict in `src/services/prompt_builder.py`
3. Add `/file` and `/url` endpoints in `src/api/routes/extract.py` with the new schema and `route_key`
4. Add tests in `tests/` mirroring existing prompt/post-processor tests

### Schema Shape

Every value-bearing field is a `BBoxField`:
```python
class BBoxField(BaseModel):
    value: Union[str, float, int, None]
    bounding_box: Optional[Tuple[int, int, int, int]]  # [xmin, ymin, xmax, ymax] in [0, 1000]
```

All responses share `{ success, data, error, metadata }`.

### Where to Look

| Question | File |
|---|---|
| Request flow | `src/api/routes/extract.py` → `src/services/vlm_processor.py` |
| What the model sees | `src/services/prompt_builder.py` |
| Hallucination detection | `src/services/post_processor.py` |
| Response shape | `src/schemas/<doc_type>.py` |
| Deployment config | `docker-compose.yml` |
| Tunable settings | `src/core/config.py` |
| In-progress design notes | `improvement.md`, `draft.md`, `draft.txt` |
