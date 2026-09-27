"""
genai_pipeline/groq_client.py
Thin, real wrapper around the Groq chat-completions API. Sends a
system+user prompt, asks for a JSON object back, and returns the raw
response text (parsing/validation happens in generator.py).
"""

from groq import Groq
from config.settings import settings


class GroqClientError(Exception):
    """Raised when a Groq API call fails (network error, bad key, model error, etc.)."""
    pass


_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise GroqClientError("GROQ_API_KEY is not configured in .env")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def call_groq(system_prompt: str, user_prompt: str, model: str) -> str:
    """
    Sends one chat-completion request to Groq and returns the assistant's
    raw text content. Requests JSON-object mode so the model is constrained
    to return valid JSON where the model supports it; falls back to a plain
    request if the model rejects the response_format parameter.
    """
    client = _get_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.GROQ_TEMPERATURE,
            max_tokens=settings.GROQ_MAX_TOKENS,
            timeout=settings.GROQ_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        # Some models/accounts don't support response_format -- retry without it
        # before treating this as a real failure.
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=settings.GROQ_TEMPERATURE,
                max_tokens=settings.GROQ_MAX_TOKENS,
                timeout=settings.GROQ_TIMEOUT_SECONDS,
            )
        except Exception as e2:
            raise GroqClientError(f"Groq API call failed for model '{model}': {str(e2)}")

    if not response.choices:
        raise GroqClientError(f"Groq API returned no choices for model '{model}'")

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise GroqClientError(f"Groq API returned empty content for model '{model}'")

    return content