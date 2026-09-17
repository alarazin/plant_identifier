"""Response schemas for identification and care.

Identification includes ranked candidates, taxonomy, confidence buckets and
visible features. Gemini receives the schema as a response constraint."""

CANDIDATE_PROPS = {
    "common_name": {"type": "string", "description": "Everyday English name."},
    "scientific_name": {
        "type": "string",
        "description": "Latin binomial. Use 'uncertain' if not confident to species level.",
    },
    "genus": {"type": "string"},
    "family": {"type": "string"},
    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "diagnostic_features": {
        "type": "array",
        "items": {"type": "string"},
        "description": "2-4 features VISIBLE IN THIS PHOTO that support this ID.",
    },
}

IDENTIFY_SCHEMA = {
    "type": "object",
    "propertyOrdering": ["is_plant", "image_quality", "quality_hint", "candidates"],
    "required": ["is_plant", "image_quality", "candidates"],
    "properties": {
        "is_plant": {
            "type": "boolean",
            "description": "False for animals, objects, people, screenshots, empty scenes.",
        },
        "image_quality": {
            "type": "string",
            "enum": ["good", "blurry", "too_far", "occluded", "dark"],
        },
        "quality_hint": {
            "type": "string",
            "description": "If quality is not 'good', one short actionable sentence for a retake.",
        },
        "candidates": {
            "type": "array",
            "description": "1-3 candidates, most likely first. Empty if is_plant is false.",
            "items": {
                "type": "object",
                "propertyOrdering": list(CANDIDATE_PROPS.keys()),
                "required": ["common_name", "scientific_name", "genus", "confidence"],
                "properties": CANDIDATE_PROPS,
            },
        },
    },
}

CARE_SCHEMA = {
    "type": "object",
    "propertyOrdering": [
        "light",
        "water",
        "humidity",
        "soil",
        "temperature",
        "toxicity",
        "common_problems",
    ],
    "required": ["light", "water", "toxicity"],
    "properties": {
        "light": {"type": "string"},
        "water": {"type": "string"},
        "humidity": {"type": "string"},
        "soil": {"type": "string"},
        "temperature": {"type": "string"},
        "toxicity": {
            "type": "string",
            "description": "Toxicity to humans, cats and dogs. Say so plainly if unknown.",
        },
        "common_problems": {"type": "array", "items": {"type": "string"}},
    },
}

SAFETY_NOTE = (
    "AI identification can be wrong. Never eat, brew, or apply a plant based on "
    "this result — confirm with an expert first."
)


def validate_response(value: object, schema: dict, path: str = "response") -> None:
    """Validate response fields against the supported JSON Schema types and rules."""
    expected = {"object": dict, "array": list, "string": str, "boolean": bool}[schema["type"]]
    if not isinstance(value, expected):
        raise ValueError(f"{path} must be {schema['type']}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} has an invalid value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key} is required")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                validate_response(value[key], child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_response(item, schema["items"], f"{path}[{index}]")
