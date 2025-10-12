#!/usr/bin/env python3
"""
Health Check and Validation Script for AI Kubernetes API Generator
Tests API connectivity, environment configuration, and system dependencies
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

def check_python_version() -> Tuple[bool, str]:
    """Check Python version compatibility."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro} ✓"
    else:
        return False, f"Python {version.major}.{version.minor}.{version.micro} - requires 3.8+"

def check_dependencies() -> List[Tuple[str, bool, str]]:
    """Check required Python dependencies."""
    deps = [
        ("openai", "OpenAI API client"),
        ("pydantic", "Data validation"),
        ("rich", "Terminal formatting"),
        ("yaml", "YAML processing"),
        ("pathlib", "Path handling (built-in)"),
    ]

    results = []
    for module, description in deps:
        try:
            if module == "pathlib":
                results.append((module, True, f"{description} ✓"))
            else:
                __import__(module)
                results.append((module, True, f"{description} ✓"))
        except ImportError:
            results.append((module, False, f"{description} - MISSING"))

    return results

def check_environment_variables() -> List[Tuple[str, bool, str]]:
    """Check environment configuration."""
    env_vars = [
        ("OPENROUTER_API_KEY", "OpenRouter API authentication"),
        ("OPENROUTER_MODEL", "OpenRouter model selection"),
        ("GITHUB_TOKEN", "GitHub API token"),
        ("GITHUB_USERNAME", "GitHub username"),
    ]

    results = []
    for var, description in env_vars:
        value = os.getenv(var)
        if value:
            if "API_KEY" in var:
                masked = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
                results.append((var, True, f"{description} - {masked} ✓"))
            else:
                results.append((var, True, f"{description} - {value} ✓"))
        else:
            status = "REQUIRED" if "API_KEY" in var else "OPTIONAL"
            results.append((var, False, f"{description} - NOT SET ({status})"))

    return results

def test_openrouter_connection() -> Tuple[bool, str]:
    """Test OpenRouter API connection."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return False, "No OPENROUTER_API_KEY found"

    try:
        # Try to import and test
        sys.path.insert(0, 'src')
        from ai_platform_generator.agent import PlatformExtensionAgent

        agent = PlatformExtensionAgent(api_key=api_key)
        return True, "OpenRouter connection successful"

    except ImportError as e:
        return False, f"Missing dependencies: {e}"
    except Exception as e:
        return False, f"Connection failed: {e}"

def check_project_structure() -> List[Tuple[str, bool, str]]:
    """Check project directory structure."""
    required_dirs = [
        ("src", "Source code directory"),
        ("examples", "Example scripts"),
        ("docs", "Documentation"),
        ("tests", "Test files"),
    ]

    results = []
    for dir_name, description in required_dirs:
        if Path(dir_name).exists():
            results.append((dir_name, True, f"{description} ✓"))
        else:
            results.append((dir_name, False, f"{description} - MISSING"))

    return results

def run_health_check() -> Dict:
    """Run comprehensive health check."""
    print("🔍 AI Kubernetes API Generator - Health Check")
    print("=" * 60)

    results = {
        "python_version": check_python_version(),
        "dependencies": check_dependencies(),
        "environment": check_environment_variables(),
        "openrouter_connection": test_openrouter_connection(),
        "project_structure": check_project_structure(),
    }

    return results

def display_results(results: Dict):
    """Display health check results."""
    # Python Version
    success, msg = results["python_version"]
    status = "✅" if success else "❌"
    print(f"\n{status} Python Version: {msg}")

    # Dependencies
    print(f"\n📦 Dependencies:")
    for dep, success, msg in results["dependencies"]:
        status = "✅" if success else "❌"
        print(f"  {status} {dep}: {msg}")

    # Environment Variables
    print(f"\n🔧 Environment Configuration:")
    for var, success, msg in results["environment"]:
        status = "✅" if success else "⚠️"
        print(f"  {status} {var}: {msg}")

    # Project Structure
    print(f"\n📁 Project Structure:")
    for dir_name, success, msg in results["project_structure"]:
        status = "✅" if success else "❌"
        print(f"  {status} {dir_name}: {msg}")

    # OpenRouter Connection
    success, msg = results["openrouter_connection"]
    status = "✅" if success else "❌"
    print(f"\n{status} OpenRouter API: {msg}")

    # Overall Status
    print("\n" + "=" * 60)
    critical_issues = []

    if not results["python_version"][0]:
        critical_issues.append("Python version")

    failed_deps = [d for d, success, _ in results["dependencies"] if not success and d != "pathlib"]
    if failed_deps:
        critical_issues.append(f"Missing dependencies: {', '.join(failed_deps)}")

    if not results["environment"][0][1]:  # OPENROUTER_API_KEY
        critical_issues.append("OpenRouter API key")

    if not results["openrouter_connection"][0]:
        critical_issues.append("OpenRouter connection")

    if critical_issues:
        print("❌ CRITICAL ISSUES FOUND:")
        for issue in critical_issues:
            print(f"   • {issue}")
        print("\n🔧 Fix these issues to use the AI generator:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Set environment variables: cp .env.example .env")
        print("   3. Edit .env with your API keys")
        return False
    else:
        print("✅ ALL CHECKS PASSED - System ready!")
        return True

def main():
    """Main health check function."""
    results = run_health_check()
    success = display_results(results)

    if not success:
        print(f"\n💡 For demo mode without API setup, run:")
        print(f"   python3 examples/impressive_ai_demo.py")

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()