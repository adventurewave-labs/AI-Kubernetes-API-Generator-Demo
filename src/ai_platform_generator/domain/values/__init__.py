"""Domain value objects."""

from __future__ import annotations

from ai_platform_generator.domain.values.checksum import Checksum
from ai_platform_generator.domain.values.group import Group
from ai_platform_generator.domain.values.gvk import GVK
from ai_platform_generator.domain.values.intent import Intent
from ai_platform_generator.domain.values.kind import Kind
from ai_platform_generator.domain.values.output_path import OutputPath
from ai_platform_generator.domain.values.property_constraints import PropertyConstraints
from ai_platform_generator.domain.values.property_type import PropertyType
from ai_platform_generator.domain.values.provider_mode import ProviderMode
from ai_platform_generator.domain.values.run_id import RunId
from ai_platform_generator.domain.values.spec_property import SpecProperty
from ai_platform_generator.domain.values.version import Stability, Version

__version__ = "0.1.0"

__all__ = [
    "GVK",
    "Checksum",
    "Group",
    "Intent",
    "Kind",
    "OutputPath",
    "PropertyConstraints",
    "PropertyType",
    "ProviderMode",
    "RunId",
    "SpecProperty",
    "Stability",
    "Version",
    "__version__",
]
