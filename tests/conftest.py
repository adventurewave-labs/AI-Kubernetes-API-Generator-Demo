"""Pytest configuration.

Six test files under tests/ target the hexagonal-architecture package
(src/main.py, src/agent/, src/codegen/, src/validation/) that was built on
the `claude/adr-ddd-documentation-wcROb` branch and never merged to main.
They fail at collection on main because those modules do not exist here,
so they are excluded from the default run rather than deleted.

The suite that runs on main: test_agent.py, test_codegen.py, test_cli.py.
"""

import sys
from pathlib import Path

# Make `from src.ai_platform_generator...` imports resolvable for both
# `python -m pytest tests/` and bare `pytest tests/` (the run.sh invocation).
sys.path.insert(0, str(Path(__file__).parent.parent))

collect_ignore = [
    "e2e/test_complete_workflow.py",            # imports `main` (unmerged branch)
    "integration/test_openapi_codegen.py",      # imports `docker` (unmerged branch harness)
    "performance/test_codegen_performance.py",  # imports `psutil` (unmerged branch harness)
    "unit/agent/test_agent_core.py",            # imports `agent.agent_core` (unmerged branch)
    "unit/codegen/test_spec_parser.py",         # imports `codegen` (unmerged branch)
    "validation/test_go_project_validation.py",  # imports `validation.go_validator` (unmerged branch)
]
