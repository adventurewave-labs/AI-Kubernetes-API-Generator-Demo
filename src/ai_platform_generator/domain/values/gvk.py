"""GVK (Group / Version / Kind) value object.

The triple that uniquely identifies a Kubernetes API in the cluster.

See ``docs/ddd/04-tactical-design.md`` section 2.4 for the contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_platform_generator.domain.values.group import Group
from ai_platform_generator.domain.values.kind import Kind
from ai_platform_generator.domain.values.version import Version


@dataclass(frozen=True, slots=True)
class GVK:
    """An immutable Group/Version/Kind triple.

    Components are validated by their respective value objects, so a
    ``GVK`` instance is always well-formed.
    """

    group: Group
    version: Version
    kind: Kind

    @property
    def crd_name(self) -> str:
        """The CRD ``metadata.name`` for this GVK: ``<plural>.<group>``."""
        return f"{self.kind.plural}.{self.group}"

    @property
    def api_version(self) -> str:
        """The Kubernetes ``apiVersion`` field: ``<group>/<version>``."""
        return f"{self.group}/{self.version}"
