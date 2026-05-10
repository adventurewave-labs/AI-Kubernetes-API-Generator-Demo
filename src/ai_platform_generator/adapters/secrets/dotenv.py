"""``.env``-file :class:`SecretProvider` adapter.

Backed by ``python-dotenv``'s :func:`dotenv_values` (deliberately not
:func:`load_dotenv`): the file is parsed into a private mapping rather
than written into :data:`os.environ`, so the process environment is
never silently mutated. ADR-0012 lists this as a per-request opt-in,
so the calling layer is responsible for deciding whether to wire it
into the chain.

The file is read **lazily** on first :meth:`get` / :meth:`names` call so
that constructing the provider at module-import time is cheap and side-
effect-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class DotenvSecretProvider:
    """Resolve secrets from a ``.env`` file without mutating ``os.environ``.

    Parameters
    ----------
    path:
        Path to the dotenv file. Defaults to ``./.env``. A missing file
        is tolerated — the provider behaves as if it contained no keys.
    override:
        Documented for forwards compatibility. Always defaults to
        ``False``: this adapter never writes back to :data:`os.environ`,
        regardless of this flag. Kept on the constructor so future
        deployments can opt into a different policy via configuration.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        override: bool = False,
    ) -> None:
        self._path: Path = path if path is not None else Path(".env")
        self._override: bool = override
        self._values: dict[str, str | None] | None = None

    # ------------------------------------------------------------------
    # SecretProvider protocol
    # ------------------------------------------------------------------
    def get(self, name: str) -> str | None:
        if not isinstance(name, str):
            return None
        values = self._ensure_loaded()
        value = values.get(name)
        return value if value else None

    def names(self) -> list[str]:
        return sorted(self._ensure_loaded().keys())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> dict[str, str | None]:
        if self._values is None:
            self._values = self._read()
        return self._values

    def _read(self) -> dict[str, str | None]:
        if not self._path.is_file():
            return {}
        try:
            from dotenv import dotenv_values  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - python-dotenv ships in dev deps
            return self._fallback_parse()
        result: dict[str, Any] = dict(dotenv_values(self._path))
        # ``dotenv_values`` returns ``str | None``; preserve the shape.
        return {str(k): (None if v is None else str(v)) for k, v in result.items()}

    def _fallback_parse(self) -> dict[str, str | None]:
        """Hand-rolled minimal parser used only when python-dotenv is absent."""
        out: dict[str, str | None] = {}
        for line in self._path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            out[key] = value or None
        return out


__all__ = ["DotenvSecretProvider"]
