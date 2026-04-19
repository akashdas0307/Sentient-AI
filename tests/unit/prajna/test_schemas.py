"""Unit tests for Pydantic schemas (src/sentient/prajna/frontal/schemas.py).

Tests schema generation, validation, and integration with InferenceGateway.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentient.prajna.frontal.schemas import (
    CognitiveCoreResponse,
    DecisionAction,
    DimensionAssessment,
    DimensionAssessments,
    MemoryCandidate,
    ReflectionBlock,
    WorldModelVerdict,
)


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

def test_decision_action_respond_text() -> None:
    """DecisionAction with type=respond and text field validates."""
    action = DecisionAction(type="respond", text="Hello, world!", priority="high")
    assert action.type == "respond"
    assert action.text == "Hello, world!"
    assert action.priority == "high"


def test_decision_action_delegate_goal() -> None:
    """DecisionAction with type=delegate and goal/context fields validates."""
    action = DecisionAction(
        type="delegate",
        goal="Write a report",
        context="Akash asked for a progress update",
        success_criteria='["report sent", "format: markdown"]',
        rationale="Direct request from primary human",
        priority="high",
    )
    assert action.type == "delegate"
    assert action.goal == "Write a report"
    assert action.context == "Akash asked for a progress update"
    assert action.rationale == "Direct request from primary human"


def test_decision_action_default_priority() -> None:
    """DecisionAction defaults priority to medium."""
    action = DecisionAction(type="wait")
    assert action.priority == "medium"


def test_memory_candidate_defaults() -> None:
    """MemoryCandidate defaults importance to 0.5."""
    mc = MemoryCandidate(type="episodic", content="Had a good conversation today")
    assert mc.importance == 0.5


def test_reflection_block_defaults() -> None:
    """ReflectionBlock defaults confidence to 0.0."""
    block = ReflectionBlock()
    assert block.confidence == 0.0
    assert block.novelty == 0.5
    assert block.uncertainties == []
    assert block.memory_candidates == []


def test_dimension_assessment_defaults() -> None:
    """DimensionAssessment defaults score to 0.5 and notes to empty."""
    da = DimensionAssessment()
    assert da.score == 0.5
    assert da.notes == ""


def test_dimension_assessments_five_named_fields() -> None:
    """DimensionAssessments has exactly five named fields."""
    da = DimensionAssessments()
    assert hasattr(da, "feasibility")
    assert hasattr(da, "consequence")
    assert hasattr(da, "ethics")
    assert hasattr(da, "consistency")
    assert hasattr(da, "reality_grounding")
    # Verify they're DimensionAssessment instances
    assert isinstance(da.feasibility, DimensionAssessment)
    assert isinstance(da.consequence, DimensionAssessment)


def test_world_model_verdict_revolution_requested() -> None:
    """WorldModelVerdict with verdict=revision_requested validates."""
    verdict = WorldModelVerdict(
        verdict="revision_requested",
        revision_guidance="Make the email tone more formal",
        confidence=0.6,
    )
    assert verdict.verdict == "revision_requested"
    assert verdict.confidence == 0.6


def test_world_model_verdict_vetoed() -> None:
    """WorldModelVerdict with verdict=vetoed validates with veto_reason."""
    verdict = WorldModelVerdict(
        verdict="vetoed",
        veto_reason="Action violates constitutional principle: no irreversible actions without approval",
        confidence=0.9,
    )
    assert verdict.verdict == "vetoed"
    assert "constitutional" in verdict.veto_reason


def test_cognitive_core_response_full() -> None:
    """Full CognitiveCoreResponse validates end-to-end."""
    response = CognitiveCoreResponse(
        monologue="I should respond to Akash's question about the project.",
        assessment="Direct question from primary human about ongoing work.",
        decisions=[
            DecisionAction(type="respond", text="The project is on track.", priority="high"),
        ],
        reflection=ReflectionBlock(
            confidence=0.8,
            uncertainties=["Akash may have additional context not in the conversation"],
            novelty=0.3,
            memory_candidates=[
                MemoryCandidate(type="episodic", content="Akash asked about project status", importance=0.7),
            ],
        ),
    )
    assert response.monologue != ""
    assert len(response.decisions) == 1
    assert response.decisions[0].type == "respond"


# ---------------------------------------------------------------------------
# model_json_schema() generation (for litellm)
# ---------------------------------------------------------------------------

def test_cognitive_core_response_schema_valid() -> None:
    """CognitiveCoreResponse.model_json_schema() produces a valid dict."""
    schema = CognitiveCoreResponse.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "monologue" in schema["properties"]
    assert "decisions" in schema["properties"]
    assert "reflection" in schema["properties"]


def test_world_model_verdict_schema_valid() -> None:
    """WorldModelVerdict.model_json_schema() produces a valid dict."""
    schema = WorldModelVerdict.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "verdict" in schema["properties"]
    assert "dimension_assessments" in schema["properties"]


def test_decision_action_schema_contains_literal_type() -> None:
    """DecisionAction schema has Literal enum for type field."""
    schema = DecisionAction.model_json_schema()
    props = schema["properties"]
    assert "type" in props
    # Pydantic encodes Literal as enum with known possible values
    assert "enum" in props["type"] or "$ref" in props["type"]


# ---------------------------------------------------------------------------
# model_validate_json() — round-trip validation
# ---------------------------------------------------------------------------

def test_cognitive_core_response_roundtrip() -> None:
    """CognitiveCoreResponse validates a correct JSON string."""
    json_str = """{
        "monologue": "Thinking about the response",
        "assessment": "Simple question",
        "decisions": [
            {"type": "respond", "text": "Hello", "priority": "medium"}
        ],
        "reflection": {
            "confidence": 0.7,
            "uncertainties": [],
            "novelty": 0.5,
            "memory_candidates": []
        }
    }"""
    validated = CognitiveCoreResponse.model_validate_json(json_str)
    assert validated.monologue == "Thinking about the response"
    assert validated.decisions[0].text == "Hello"


def test_world_model_verdict_roundtrip() -> None:
    """WorldModelVerdict validates a correct JSON string."""
    json_str = """{
        "verdict": "approved",
        "dimension_assessments": {
            "feasibility": {"score": 0.8, "notes": "Can do"},
            "consequence": {"score": 0.7, "notes": "Low impact"},
            "ethics": {"score": 0.9, "notes": "No issues"},
            "consistency": {"score": 0.85, "notes": "Aligned"},
            "reality_grounding": {"score": 0.75, "notes": "Reasonable"}
        },
        "advisory_notes": "Consider being more concise",
        "revision_guidance": "",
        "veto_reason": "",
        "confidence": 0.8
    }"""
    validated = WorldModelVerdict.model_validate_json(json_str)
    assert validated.verdict == "approved"
    assert validated.dimension_assessments.feasibility.score == 0.8


def test_world_model_verdict_null_fields_coerced() -> None:
    """WorldModelVerdict coerces null revision_guidance/veto_reason to empty string.

    LLMs (especially minimax) return null for inapplicable string fields
    instead of empty string. The schema must accept null and coerce to "".
    """
    json_str = '{"verdict": "approved", "revision_guidance": null, "veto_reason": null}'
    validated = WorldModelVerdict.model_validate_json(json_str)
    assert validated.verdict == "approved"
    assert validated.revision_guidance == ""
    assert validated.veto_reason == ""


def test_invalid_verdict_rejected() -> None:
    """WorldModelVerdict rejects invalid verdict values."""
    json_str = '{"verdict": "approvedd", "confidence": 0.5}'
    with pytest.raises(Exception):  # pydantic ValidationError
        WorldModelVerdict.model_validate_json(json_str)


def test_invalid_priority_rejected() -> None:
    """DecisionAction rejects invalid priority values."""
    json_str = '{"type": "respond", "text": "Hi", "priority": "urgent"}'
    with pytest.raises(Exception):
        DecisionAction.model_validate_json(json_str)


def test_missing_required_field_rejected() -> None:
    """CognitiveCoreResponse rejects missing required fields."""
    json_str = '{"monologue": "test"}'  # missing assessment, decisions, reflection
    with pytest.raises(Exception):
        CognitiveCoreResponse.model_validate_json(json_str)


# ---------------------------------------------------------------------------
# InferenceGateway schema enforcement (mocked)
# ---------------------------------------------------------------------------

def test_inference_gateway_ollama_chat_prefix() -> None:
    """When response_format is provided, ollama_chat/ prefix is used."""
    from sentient.core.inference_gateway import InferenceGateway, InferenceRequest

    gw = InferenceGateway({
        "models": {
            "test-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            },
        },
    })
    gw._litellm = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"monologue":"test","assessment":"ok","decisions":[],"reflection":{"confidence":0.0,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    gw._litellm.acompletion = AsyncMock(return_value=mock_response)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="test-model",
        prompt="test",
        response_format=CognitiveCoreResponse,
    )

    import asyncio
    asyncio.get_event_loop().run_until_complete(gw.infer(request))

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["model"] == "ollama_chat/llama3.2:3b"


def test_inference_gateway_response_format_passed() -> None:
    """When response_format is provided, response_format dict is passed to litellm."""
    from sentient.core.inference_gateway import InferenceGateway, InferenceRequest

    gw = InferenceGateway({
        "models": {
            "test-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            },
        },
    })
    gw._litellm = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"monologue":"test","assessment":"ok","decisions":[],"reflection":{"confidence":0.0,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    gw._litellm.acompletion = AsyncMock(return_value=mock_response)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="test-model",
        prompt="test",
        response_format=CognitiveCoreResponse,
    )

    import asyncio
    asyncio.get_event_loop().run_until_complete(gw.infer(request))

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert "response_format" in call_kwargs
    rf = call_kwargs["response_format"]
    assert rf["type"] == "json_schema"
    assert "schema" in rf["json_schema"]


def test_inference_gateway_temperature_override() -> None:
    """When response_format is provided, temperature is overridden to 0."""
    from sentient.core.inference_gateway import InferenceGateway, InferenceRequest

    gw = InferenceGateway({
        "models": {
            "test-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            },
        },
    })
    gw._litellm = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"monologue":"test","assessment":"ok","decisions":[],"reflection":{"confidence":0.0,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    gw._litellm.acompletion = AsyncMock(return_value=mock_response)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="test-model",
        prompt="test",
        temperature=0.9,  # explicitly overridden to 0
        response_format=CognitiveCoreResponse,
    )

    import asyncio
    asyncio.get_event_loop().run_until_complete(gw.infer(request))

    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    assert call_kwargs["temperature"] == 0


def test_inference_gateway_validation_retries_once() -> None:
    """When validation fails, InferenceGateway retries once then raises."""
    from sentient.core.inference_gateway import InferenceGateway, InferenceRequest

    gw = InferenceGateway({
        "models": {
            "test-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            },
        },
    })
    gw._litellm = MagicMock()

    # First response invalid, second valid
    invalid_response = MagicMock()
    invalid_response.choices = [MagicMock()]
    invalid_response.choices[0].message.content = "not json at all"
    invalid_response.usage.prompt_tokens = 10
    invalid_response.usage.completion_tokens = 5

    valid_response = MagicMock()
    valid_response.choices = [MagicMock()]
    valid_response.choices[0].message.content = '{"monologue":"test","assessment":"ok","decisions":[],"reflection":{"confidence":0.0,"uncertainties":[],"novelty":0.5,"memory_candidates":[]}}'
    valid_response.usage.prompt_tokens = 10
    valid_response.usage.completion_tokens = 20

    call_count = 0

    async def mock_acompletion(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return invalid_response
        return valid_response  # Second attempt succeeds with valid JSON, so no error

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="test-model",
        prompt="test",
        response_format=CognitiveCoreResponse,
    )

    import asyncio
    # Should succeed because retry got valid JSON
    response = asyncio.get_event_loop().run_until_complete(gw.infer(request))
    assert response.error is None
    assert call_count == 2

    # Now test the failure path: both attempts return invalid JSON
    call_count = 0

    async def mock_acompletion_both_fail(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        return invalid_response

    gw._litellm.acompletion = AsyncMock(side_effect=mock_acompletion_both_fail)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request2 = InferenceRequest(
        model_label="test-model",
        prompt="test",
        response_format=CognitiveCoreResponse,
    )

    with pytest.raises(Exception, match="Structured output validation failed after retry"):
        asyncio.get_event_loop().run_until_complete(gw.infer(request2))

    # Should have tried twice
    assert call_count == 2


def test_inference_gateway_no_response_format_backward_compat() -> None:
    """When response_format is None, behavior is unchanged (no validation, ollama_chat/ used)."""
    from sentient.core.inference_gateway import InferenceGateway, InferenceRequest

    gw = InferenceGateway({
        "models": {
            "test-model": {
                "primary": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            },
        },
    })
    gw._litellm = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "plain text response"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    gw._litellm.acompletion = AsyncMock(return_value=mock_response)
    gw._litellm.completion_cost = MagicMock(return_value=0.0)

    request = InferenceRequest(
        model_label="test-model",
        prompt="test",
        # No response_format
    )

    import asyncio
    response = asyncio.get_event_loop().run_until_complete(gw.infer(request))

    assert response.text == "plain text response"
    call_kwargs = gw._litellm.acompletion.call_args.kwargs
    # ollama_chat/ is still used for all ollama calls
    assert call_kwargs["model"] == "ollama_chat/llama3.2:3b"
    # No response_format in call
    assert "response_format" not in call_kwargs
    # temperature is the endpoint default, not forced to 0
    assert call_kwargs["temperature"] == 0.7