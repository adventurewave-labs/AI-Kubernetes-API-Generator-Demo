"""Each fake/in-memory adapter must satisfy its port Protocol.

The check is twofold:

* For ports decorated ``@runtime_checkable`` we use ``isinstance``,
  which catches missing attributes/methods at runtime.
* For *every* port we additionally pass the adapter through
  ``typing.cast`` and assign it to a variable annotated with the port
  type. That gives ``mypy --strict`` a chance to flag a structural
  mismatch even when ``runtime_checkable`` is not present.
"""

from __future__ import annotations

from typing import cast

from ai_platform_generator.adapters.clock.frozen import FrozenClock
from ai_platform_generator.adapters.clock.system import SystemClock
from ai_platform_generator.adapters.llm.fake import FakeLlmAdapter
from ai_platform_generator.adapters.repo.in_memory import InMemoryArtifactRepository
from ai_platform_generator.adapters.runtime.fake import FakeClusterRuntime
from ai_platform_generator.adapters.secrets.in_memory import InMemorySecretProvider
from ai_platform_generator.adapters.telemetry.multi import MultiSink
from ai_platform_generator.adapters.telemetry.noop import NoopSink
from ai_platform_generator.adapters.telemetry.recording import RecordingSink
from ai_platform_generator.ports.artifact_repository import ArtifactRepository
from ai_platform_generator.ports.clock import Clock
from ai_platform_generator.ports.cluster_runtime import ClusterRuntime
from ai_platform_generator.ports.llm_provider import LlmProvider
from ai_platform_generator.ports.secret_provider import SecretProvider
from ai_platform_generator.ports.telemetry_sink import TelemetrySink


def test_fake_llm_adapter_satisfies_port() -> None:
    adapter = FakeLlmAdapter(responses=[{"ok": True}])
    assert isinstance(adapter, LlmProvider)
    _: LlmProvider = cast(LlmProvider, adapter)


def test_in_memory_repo_satisfies_port() -> None:
    adapter = InMemoryArtifactRepository()
    assert isinstance(adapter, ArtifactRepository)
    _: ArtifactRepository = cast(ArtifactRepository, adapter)


def test_fake_runtime_satisfies_port() -> None:
    adapter = FakeClusterRuntime()
    assert isinstance(adapter, ClusterRuntime)
    _: ClusterRuntime = cast(ClusterRuntime, adapter)


def test_in_memory_secrets_satisfies_port() -> None:
    adapter = InMemorySecretProvider({"FOO": "bar"})
    assert isinstance(adapter, SecretProvider)
    _: SecretProvider = cast(SecretProvider, adapter)


def test_recording_sink_satisfies_port() -> None:
    adapter = RecordingSink()
    assert isinstance(adapter, TelemetrySink)
    _: TelemetrySink = cast(TelemetrySink, adapter)


def test_noop_sink_satisfies_port() -> None:
    adapter = NoopSink()
    assert isinstance(adapter, TelemetrySink)
    _: TelemetrySink = cast(TelemetrySink, adapter)


def test_multi_sink_satisfies_port() -> None:
    adapter = MultiSink([RecordingSink(), NoopSink()])
    assert isinstance(adapter, TelemetrySink)
    _: TelemetrySink = cast(TelemetrySink, adapter)


def test_system_clock_satisfies_port() -> None:
    adapter = SystemClock()
    assert isinstance(adapter, Clock)
    _: Clock = cast(Clock, adapter)


def test_frozen_clock_satisfies_port() -> None:
    adapter = FrozenClock()
    assert isinstance(adapter, Clock)
    _: Clock = cast(Clock, adapter)
