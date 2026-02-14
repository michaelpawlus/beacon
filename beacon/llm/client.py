"""Anthropic API client wrapper for Beacon Phase 3."""

import json
import os
import re
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

_client = None


@dataclass
class LLMResponse:
    """Response from an LLM generation call."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def get_client():
    """Get or create the Anthropic client (lazy init)."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it with: export ANTHROPIC_API_KEY=your-key-here"
        )

    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic SDK not installed. Run: pip install beacon[llm]"
        )

    _client = anthropic.Anthropic(api_key=api_key)
    return _client


def generate(
    prompt: str,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> LLMResponse:
    """Generate text from the LLM. Returns an LLMResponse."""
    client = get_client()

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)

    return LLMResponse(
        text=response.content[0].text,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def generate_structured(
    prompt: str,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict:
    """Generate a structured JSON response from the LLM.

    Strips code fences if present and parses the result as JSON.
    """
    response = generate(prompt, system=system, model=model,
                        max_tokens=max_tokens, temperature=temperature)

    text = response.text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    return json.loads(text)
