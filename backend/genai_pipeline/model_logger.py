"""
genai_pipeline/model_logger.py
Lightweight logger for every GenAI call made to Groq -- which model was
used, how long it took, whether it succeeded, and (on failure) why. Written
to both the console and a rolling log file so generation issues can be
traced after the fact.
"""

import os
import time
import logging

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("genai_pipeline")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, "genai_calls.log"))
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def log_call_start(model: str, employee_code: str):
    logger.info(f"GenAI call START | model={model} | employee={employee_code}")
    return time.time()


def log_call_success(model: str, employee_code: str, started_at: float, tokens_used: int = None):
    duration = round(time.time() - started_at, 2)
    logger.info(
        f"GenAI call SUCCESS | model={model} | employee={employee_code} | "
        f"duration={duration}s | tokens={tokens_used if tokens_used is not None else 'n/a'}"
    )


def log_call_failure(model: str, employee_code: str, started_at: float, error: str):
    duration = round(time.time() - started_at, 2)
    logger.warning(
        f"GenAI call FAILED | model={model} | employee={employee_code} | "
        f"duration={duration}s | error={error}"
    )


def log_fallback_triggered(primary_model: str, fallback_model: str, employee_code: str):
    logger.warning(
        f"GenAI FALLBACK triggered | primary={primary_model} -> fallback={fallback_model} | "
        f"employee={employee_code}"
    )


def log_schema_retry(employee_code: str, attempt: int, max_attempts: int, errors: list):
    """SRS Step 39 -- every retry caused by invalid/incomplete JSON is logged."""
    summary = "; ".join(f"{e.get('path')}: {e.get('message')}" for e in errors[:5])
    logger.warning(
        f"GenAI SCHEMA RETRY | employee={employee_code} | attempt={attempt}/{max_attempts} | "
        f"errors={len(errors)} | {summary}"
    )


def log_generation_complete(employee_code: str, prompt_version: str, model: str, attempts: int, sources: list):
    logger.info(
        f"GenAI PLAN ACCEPTED | employee={employee_code} | prompt={prompt_version} | model={model} | "
        f"attempts={attempts} | sources={','.join(s.get('document_code', '?') + '@' + str(s.get('version')) for s in sources)}"
    )
