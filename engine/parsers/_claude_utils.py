"""Shared Claude API helpers for all parsers."""

import os


def get_model_and_thinking_kwargs() -> tuple[str, dict]:
    """
    Returns (model, extra_kwargs) where extra_kwargs contains thinking config.
    Centralised so adding a new non-thinking model only requires one change.
    """
    model = os.getenv("PARSER_MODEL", "claude-opus-4-8")
    non_thinking_models = {"haiku"}
    supports_thinking = not any(m in model.lower() for m in non_thinking_models)
    extra = {"thinking": {"type": "adaptive"}} if supports_thinking else {}
    return model, extra


def safe_text_block(content: list) -> str:
    """
    Extract text from the first TextBlock in a response content list.
    Raises ValueError with a clear message if no text block is present
    (e.g. only ThinkingBlocks returned).
    """
    for block in content:
        if block.type == "text":
            return block.text
    raise ValueError(
        f"No text block in response. Blocks present: {[b.type for b in content]}"
    )
