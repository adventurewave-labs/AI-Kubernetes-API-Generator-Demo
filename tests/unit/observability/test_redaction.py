"""Tests for :mod:`ai_platform_generator.domain.observability.redaction`."""

from __future__ import annotations

import re

import pytest

from ai_platform_generator.domain.observability.redaction import (
    REDACTED,
    RedactionPolicy,
    SecretRedactor,
)


@pytest.fixture
def redactor() -> SecretRedactor:
    return SecretRedactor(RedactionPolicy.default())


class TestDefaultPatterns:
    """Each default regex from ``06-observability.md`` §9 is honoured."""

    def test_openai_key_pattern(self, redactor: SecretRedactor) -> None:
        text = "leak: sk-ABCDEFGHIJ1234567890XYZ in prompt"
        assert redactor.redact_string(text) == f"leak: {REDACTED} in prompt"

    def test_openrouter_key_pattern(self, redactor: SecretRedactor) -> None:
        text = "or-ABCDEFGHIJ1234567890ABC trailing"
        assert redactor.redact_string(text) == f"{REDACTED} trailing"

    def test_bearer_token_pattern(self, redactor: SecretRedactor) -> None:
        text = "auth: Bearer abc.def-ghi_123"
        assert redactor.redact_string(text) == f"auth: {REDACTED}"

    def test_short_sk_does_not_match(self, redactor: SecretRedactor) -> None:
        # Fewer than 20 chars after ``sk-`` is intentionally not a match.
        text = "sk-tooshort"
        assert redactor.redact_string(text) == "sk-tooshort"


class TestIdempotency:
    def test_redacting_twice_is_a_no_op(self, redactor: SecretRedactor) -> None:
        original = "sk-ABCDEFGHIJ1234567890XYZ"
        once = redactor.redact_string(original)
        twice = redactor.redact_string(once)
        assert once == twice == REDACTED

    def test_mapping_idempotent(self, redactor: SecretRedactor) -> None:
        payload = {"api_key": "sk-ABCDEFGHIJ1234567890XYZ", "note": "hi"}
        once = redactor.redact_mapping(payload)
        twice = redactor.redact_mapping(once)
        assert once == twice


class TestFromEnv:
    def test_from_env_appends_extras(self) -> None:
        env = {"AI_AGENT_REDACT_PATTERNS": "custom-[A-Z]+"}
        policy = RedactionPolicy.from_env(env=env)
        assert any(p.pattern == "custom-[A-Z]+" for p in policy.patterns)
        # Defaults still present.
        assert any(p.pattern.startswith("sk-") for p in policy.patterns)

    def test_from_env_handles_blank(self) -> None:
        policy = RedactionPolicy.from_env(env={})
        assert policy.patterns == RedactionPolicy.default().patterns

    def test_from_env_drops_invalid(self) -> None:
        env = {"AI_AGENT_REDACT_PATTERNS": "[invalid, valid-[a-z]+"}
        policy = RedactionPolicy.from_env(env=env)
        # ``valid-[a-z]+`` compiles; ``[invalid`` does not.
        compiled = [p.pattern for p in policy.patterns]
        assert "valid-[a-z]+" in compiled
        assert "[invalid" not in compiled

    def test_from_env_skips_empty_fragments(self) -> None:
        env = {"AI_AGENT_REDACT_PATTERNS": ", ,custom-[a-z]+,"}
        policy = RedactionPolicy.from_env(env=env)
        compiled = [p.pattern for p in policy.patterns]
        assert compiled.count("custom-[a-z]+") == 1


class TestNestedMapping:
    def test_nested_dict_secret_key(self, redactor: SecretRedactor) -> None:
        payload = {"outer": {"api_key": "sk-ABCDEFGHIJ1234567890XYZ", "ok": "fine"}}
        result = redactor.redact_mapping(payload)
        assert result == {"outer": {"api_key": REDACTED, "ok": "fine"}}

    def test_list_of_strings_redacted(self, redactor: SecretRedactor) -> None:
        payload = {"messages": ["hi", "Bearer abc.def-ghi"]}
        result = redactor.redact_mapping(payload)
        assert result == {"messages": ["hi", REDACTED]}

    def test_tuple_recursed(self, redactor: SecretRedactor) -> None:
        payload = {"vals": ("sk-ABCDEFGHIJ1234567890XYZ", "ok")}
        result = redactor.redact_mapping(payload)
        assert result == {"vals": (REDACTED, "ok")}

    def test_secret_key_with_nested_payload(self, redactor: SecretRedactor) -> None:
        # Whole-value redaction even when the value is a complex type —
        # this is the protection against smuggling secrets through as a
        # nested dict.
        payload = {"secret": {"inner": "value"}}
        assert redactor.redact_mapping(payload) == {"secret": REDACTED}

    def test_non_string_values_passthrough(self, redactor: SecretRedactor) -> None:
        payload = {"count": 3, "ok": True, "miss": None}
        assert redactor.redact_mapping(payload) == payload


class TestCaseInsensitiveSecretKeys:
    def test_uppercase_key(self, redactor: SecretRedactor) -> None:
        assert redactor.redact_mapping({"API_KEY": "value"}) == {"API_KEY": REDACTED}

    def test_mixed_case_key(self, redactor: SecretRedactor) -> None:
        assert redactor.redact_mapping({"Token": "x"}) == {"Token": REDACTED}

    def test_password_variant(self, redactor: SecretRedactor) -> None:
        assert redactor.redact_mapping({"PASSWORD": "x"}) == {"PASSWORD": REDACTED}


class TestPolicyConstruction:
    def test_custom_policy_used(self) -> None:
        policy = RedactionPolicy(
            patterns=(re.compile(r"hush-[a-z]+"),),
            secret_keys=("private",),
        )
        redactor = SecretRedactor(policy)
        assert redactor.redact_string("hush-abc") == REDACTED
        assert redactor.redact_mapping({"private": "x"}) == {"private": REDACTED}
        # Default keys are NOT inherited.
        assert redactor.redact_mapping({"api_key": "x"}) == {"api_key": "x"}
