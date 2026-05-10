"""Helper used as ``json.dumps(default=...)`` by :class:`JsonRenderer`.

The orchestrator passes domain objects (``Path``, ``UUID``, ``datetime``,
``Enum``, ``bytes``, Pydantic models) into events. The JSON renderer must
serialise them deterministically without reaching back into the domain.

Rules (per ``docs/ddd/bounded-contexts/05-user-interaction.md`` §5):

* :class:`pathlib.Path` → ``str(path)``.
* :class:`uuid.UUID` → ``str(uuid)``.
* :class:`datetime.datetime` → ISO-8601 with a ``Z`` suffix when the value
  is UTC (so downstream consumers do not need to parse offsets).
* :class:`enum.Enum` → ``.value``.
* :class:`bytes` → base64 ASCII (URL-safe is *not* used because the wire
  format is JSON, not a URL).
* Pydantic ``BaseModel`` → ``.model_dump(mode="json")``.
* Anything else → ``{"_unserialisable": True, "repr": repr(obj)}``. We
  never raise: dropping a single field must not break log shipping.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePath
from typing import Any
from uuid import UUID

try:  # pragma: no cover - import guard
    from pydantic import BaseModel
except Exception:  # pragma: no cover - pydantic is a hard dep but be defensive
    BaseModel = None  # type: ignore[assignment,misc]


def _json_default(obj: Any) -> Any:
    """Return a JSON-serialisable representation of *obj*.

    Designed for use as the ``default=`` argument to :func:`json.dumps`.
    Never raises: unknown types are returned with an ``_unserialisable``
    marker so the line stays valid JSON.
    """
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        # Render UTC as ``…Z``; preserve any explicit offset for non-UTC.
        if obj.tzinfo is not None and obj.utcoffset() == timezone.utc.utcoffset(obj):
            return obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(obj)).decode("ascii")
    if BaseModel is not None and isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, set | frozenset):
        return sorted(obj, key=repr)
    return {"_unserialisable": True, "repr": repr(obj)}


__all__ = ["_json_default"]
