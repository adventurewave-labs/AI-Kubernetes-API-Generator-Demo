"""ProviderMode enum.

Whether a generation run uses a real LLM (``LIVE``) or the deterministic
in-process demo catalogue (``DEMO``). Captured in the provenance
manifest so consumers can tell synthetic outputs from real ones.

See ``docs/ddd/04-tactical-design.md`` section 2.10 for the contract.
"""

from __future__ import annotations

from enum import StrEnum


class ProviderMode(StrEnum):
    """Operating mode of the LLM provider for a generation run."""

    LIVE = "live"
    DEMO = "demo"
