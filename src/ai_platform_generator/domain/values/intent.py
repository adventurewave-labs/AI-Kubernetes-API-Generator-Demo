"""Intent value object.

The user's natural-language request, captured verbatim before any
LLM-driven parsing or normalisation. ``Intent`` is the *input* to the
Intent Interpretation context (see
``docs/ddd/02-ubiquitous-language.md``) and the *output* of User
Interaction.

See ``docs/ddd/04-tactical-design.md`` section 3.1 (``GenerationRun``)
for where ``Intent`` is consumed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from ai_platform_generator.domain.errors import InvalidIntent

#: Maximum acceptable intent length, measured in characters of the
#: *stripped* text. 8 KiB of UTF-8 is well above any reasonable user
#: prompt and well below any LLM context window we target.
_MAX_LEN = 8192


@dataclass(frozen=True, slots=True)
class Intent:
    """An immutable wrapper around free-text user input.

    Parameters
    ----------
    text:
        The raw natural-language intent. Must contain at least one
        non-whitespace character after stripping, and at most 8192
        characters of stripped content.
    submitted_at:
        The wall-clock instant the intent was received. Stored to
        give the orchestrator a stable creation timestamp independent
        of the run's start time.
    """

    text: str
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise InvalidIntent(f"text must be a str, got {type(self.text)!r}")
        stripped = self.text.strip()
        if len(stripped) < 1:
            raise InvalidIntent("intent text must be non-empty after stripping")
        if len(stripped) > _MAX_LEN:
            raise InvalidIntent(
                f"intent text must be at most {_MAX_LEN} characters, "
                f"got {len(stripped)}"
            )
        if not isinstance(self.submitted_at, datetime):
            raise InvalidIntent(
                f"submitted_at must be a datetime, got {type(self.submitted_at)!r}"
            )

    def text_hash(self) -> str:
        """SHA-256 hex digest of the raw text.

        Useful for de-duplicating identical prompts in telemetry while
        keeping the prompt itself out of the metric stream.
        """
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()
