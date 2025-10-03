"""
AI-Assisted Platform Extension Generator

An AI agent that accelerates Kubernetes platform development through
natural language to code generation.
"""

__version__ = "0.1.0"
__author__ = "AI Assistant"
__email__ = "ai@example.com"

from .agent import PlatformExtensionAgent
from .codegen import CodeGenerator
from .cli import main

__all__ = ["PlatformExtensionAgent", "CodeGenerator", "main"]