"""Model input builders and fallback order.

Gemini accepts a response schema. OpenAI providers receive the schema in the
prompt. The backend validates responses from every provider."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable

from .prompts import CARE_SYSTEM, IDENTIFY_PROMPT, IDENTIFY_SYSTEM, care_prompt
from .schema import CARE_SCHEMA, IDENTIFY_SCHEMA

# Model used by the OpenAI completion wrapper.
OPENAI_ROUTER_MODEL = os.getenv("OPENAI_ROUTER_MODEL", "gpt-5.1")

_QUALITY = set(IDENTIFY_SCHEMA["properties"]["image_quality"]["enum"])
_CONFIDENCE = {"high", "medium", "low"}


def _json_only(schema: dict) -> str:
    """Ask for the schema in prose, for models that cannot be handed one."""
    return (
        "\n\nReturn ONLY a JSON object and nothing else — no markdown fence, no "
        "commentary before or after. It must validate against this JSON Schema:\n"
        + json.dumps(schema, separators=(",", ":"))
    )


# ---- input builders, one per model's parameter names -----------------------


def _gemini_identify(image_url: str) -> dict:
    """Build the primary model identification input."""
    return {
        "prompt": IDENTIFY_PROMPT,
        "system_instruction": IDENTIFY_SYSTEM,
        "media_urls": [image_url],
        "response_mime_type": "application/json",
        "response_schema": IDENTIFY_SCHEMA,
        "thinking_budget": 0,  # avoids the $2.50/M "thoughts" token charge
        "temperature": 0.1,    # Keep output variation low
        "max_output_tokens": 1500,
    }


def _gemini_care(scientific_name: str, common_name: str) -> dict:
    return {
        "prompt": care_prompt(scientific_name, common_name),
        "system_instruction": CARE_SYSTEM,
        "response_mime_type": "application/json",
        "response_schema": CARE_SCHEMA,
        "thinking_budget": 0,
        "temperature": 0.2,
        "max_output_tokens": 900,
    }


def _chatgpt5_identify(image_url: str) -> dict:
    return {
        "user_prompt": IDENTIFY_PROMPT + _json_only(IDENTIFY_SCHEMA),
        "system_prompt": IDENTIFY_SYSTEM,
        "image_url": image_url,
        "temperature": 0.1,
        "max_output_tokens": 1500,
    }


def _chatgpt5_care(scientific_name: str, common_name: str) -> dict:
    return {
        "user_prompt": care_prompt(scientific_name, common_name) + _json_only(CARE_SCHEMA),
        "system_prompt": CARE_SYSTEM,
        "temperature": 0.2,
        "max_output_tokens": 900,
    }


def _chatcompletion_identify(image_url: str) -> dict:
    # This wrapper requires a model name and uses max_tokens.
    return {
        "user_prompt": IDENTIFY_PROMPT + _json_only(IDENTIFY_SCHEMA),
        "system_prompt": IDENTIFY_SYSTEM,
        "image_url": image_url,
        "model": OPENAI_ROUTER_MODEL,
        "temperature": 0.1,
        "max_tokens": 1500,
    }


def _chatcompletion_care(scientific_name: str, common_name: str) -> dict:
    return {
        "user_prompt": care_prompt(scientific_name, common_name) + _json_only(CARE_SCHEMA),
        "system_prompt": CARE_SYSTEM,
        "model": OPENAI_ROUTER_MODEL,
        "temperature": 0.2,
        "max_tokens": 900,
    }


@dataclass(frozen=True)
class Provider:
    slug: str
    identify_input: Callable[[str], dict]
    care_input: Callable[[str, str], dict]
    version: str = "0.0.1"
    #: Whether the provider accepts response_schema.
    schema_native: bool = False


REGISTRY: dict[str, Provider] = {
    "gemini-2-5-flash": Provider(
        "gemini-2-5-flash", _gemini_identify, _gemini_care, schema_native=True
    ),
    "openai-chatgpt-5": Provider("openai-chatgpt-5", _chatgpt5_identify, _chatgpt5_care),
    "openai-chat-completion": Provider(
        "openai-chat-completion", _chatcompletion_identify, _chatcompletion_care
    ),
}

DEFAULT_FALLBACKS = "openai-chatgpt-5,openai-chat-completion"


def gemini_like(slug: str, version: str) -> Provider:
    """Use Gemini input fields for a model slug outside the registry."""
    return Provider(slug, _gemini_identify, _gemini_care, version=version, schema_native=True)


def build_chain(primary_slug: str, primary_version: str) -> list[Provider]:
    """Primary first, then fallbacks, skipping anything unknown or duplicated."""
    primary = REGISTRY.get(primary_slug)
    if primary is None or primary.version != primary_version:
        base = REGISTRY.get(primary_slug)
        primary = (
            Provider(base.slug, base.identify_input, base.care_input, primary_version,
                     base.schema_native)
            if base
            else gemini_like(primary_slug, primary_version)
        )

    raw = os.getenv("EACHLABS_FALLBACKS", DEFAULT_FALLBACKS)
    chain = [primary]
    for slug in (s.strip() for s in raw.split(",")):
        if not slug or slug == primary.slug:
            continue
        provider = REGISTRY.get(slug)
        if provider is not None:
            chain.append(provider)
    return chain


# ---- shaping fallback output back to the contract --------------------------


def coerce_identify(result: dict) -> dict:
    """Normalize fallback candidates for the app. Reject unusable results."""
    if not isinstance(result, dict):
        raise ValueError(f"expected a JSON object, got {type(result).__name__}")

    is_plant = result.get("is_plant")
    if not isinstance(is_plant, bool):
        # Some models emit "true"/"yes" as strings.
        is_plant = str(is_plant).strip().lower() in ("true", "yes", "1")

    quality = result.get("image_quality")
    if quality not in _QUALITY:
        quality = "good"

    candidates = []
    for raw in result.get("candidates") or []:
        if not isinstance(raw, dict):
            continue
        common = str(raw.get("common_name") or "").strip()
        latin = str(raw.get("scientific_name") or "").strip()
        if not common and not latin:
            continue
        confidence = str(raw.get("confidence") or "").strip().lower()
        features = [
            str(f).strip()
            for f in (raw.get("diagnostic_features") or [])
            if str(f).strip()
        ]
        candidates.append(
            {
                "common_name": common or latin,
                "scientific_name": latin or "uncertain",
                "genus": str(raw.get("genus") or "").strip(),
                "family": str(raw.get("family") or "").strip() or None,
                # An unrecognised bucket must not read as certainty.
                "confidence": confidence if confidence in _CONFIDENCE else "low",
                "diagnostic_features": features[:4],
            }
        )

    if is_plant and not candidates:
        raise ValueError("is_plant true but no usable candidates")

    hint = result.get("quality_hint")
    return {
        "is_plant": is_plant,
        "image_quality": quality,
        "quality_hint": str(hint).strip() if hint else None,
        "candidates": candidates[:3],
    }
