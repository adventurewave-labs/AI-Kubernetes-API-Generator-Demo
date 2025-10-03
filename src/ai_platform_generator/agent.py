"""
Core AI Agent for Platform Extension Generation

This module contains the main AI agent logic that interprets natural language
requests and translates them into code generation commands.
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import openai
from pydantic import BaseModel, Field


@dataclass
class CodegenRequest:
    """Represents a code generation request parsed from natural language."""
    group: str = "platform.cnoe.io"
    version: str = "v1alpha1"
    kind: str = ""
    spec_properties: Dict[str, str] = Field(default_factory=dict)
    output_dir: str = "/tmp/generated"
    description: str = ""


class PlatformExtensionAgent:
    """AI Agent for generating Kubernetes platform extensions."""

    def __init__(self, api_key: Optional[str] = None, model: str = "anthropic/claude-3.5-sonnet"):
        """Initialize the agent with OpenRouter configuration."""
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        self.model = model
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI agent."""
        return """
You are an expert Kubernetes Platform Engineering assistant. Your sole purpose is to translate natural language requests for new Kubernetes APIs into the precise JSON needed for code generation tools.

The user will describe an API they want. You must parse their request for the following information:
1. **group**: A reverse-DNS style group name (e.g., `platform.acme.io`). Default to `platform.cnoe.io` if not specified.
2. **version**: The API version (e.g., `v1alpha1`). Default to `v1alpha1`.
3. **kind**: The CamelCase name of the resource (e.g., `VectorDB`, `CacheCluster`).
4. **spec properties**: The fields inside the `.spec` of the resource. You must infer the type (string, integer, boolean).

You MUST format your response as a single, minified JSON object containing the complete request specification.

Example User Request: "I need a `Notebook` CRD for our data science team. It should have a `cpu` field and a `memory` field, both strings."

Your Expected JSON Response:
{
  "group": "datascience.cnoe.io",
  "version": "v1alpha1",
  "kind": "Notebook",
  "spec_properties": {
    "cpu": {"type": "string"},
    "memory": {"type": "string"}
  },
  "output_dir": "/tmp/notebook",
  "description": "Kubernetes Notebook CRD for data science workloads with CPU and memory specifications"
}

Example User Request: "Make me a simple `ClusterClaim` API with a `clusterId` string field."

Your Expected JSON Response:
{
  "group": "platform.cnoe.io",
  "version": "v1alpha1",
  "kind": "ClusterClaim",
  "spec_properties": {
    "clusterId": {"type": "string"}
  },
  "output_dir": "/tmp/clusterclaim",
  "description": "Simple ClusterClaim API for cluster resource management"
}

Important rules:
- Always infer appropriate types: string for text, integer for numbers, boolean for true/false values
- Use CamelCase for kind names
- Use reverse-DNS naming for groups
- Generate reasonable output directory names based on the kind
- Include a brief description of what the API does
- Respond with ONLY the JSON object, no additional text
"""

    def parse_request(self, user_input: str) -> CodegenRequest:
        """
        Parse natural language input into a structured codegen request.

        Args:
            user_input: Natural language description of the desired API

        Returns:
            CodegenRequest: Structured request for code generation

        Raises:
            ValueError: If the AI response cannot be parsed
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from AI model")

            data = json.loads(content)

            # Convert string types to proper type format
            if "spec_properties" in data:
                spec_props = {}
                for prop_name, prop_info in data["spec_properties"].items():
                    if isinstance(prop_info, str):
                        spec_props[prop_name] = {"type": prop_info}
                    elif isinstance(prop_info, dict) and "type" in prop_info:
                        spec_props[prop_name] = prop_info
                    else:
                        spec_props[prop_name] = {"type": "string"}  # default
                data["spec_properties"] = spec_props

            return CodegenRequest(**data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except Exception as e:
            raise ValueError(f"Error processing AI response: {e}")

    def validate_request(self, request: CodegenRequest) -> List[str]:
        """
        Validate a parsed codegen request.

        Args:
            request: The parsed request to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        if not request.kind:
            errors.append("Kind is required")
        elif not re.match(r'^[A-Z][a-zA-Z0-9]*$', request.kind):
            errors.append("Kind must be CamelCase (e.g., VectorDB, MyResource)")

        if not request.group:
            errors.append("Group is required")
        elif not re.match(r'^[a-z0-9.-]+\.[a-z0-9.-]+$', request.group):
            errors.append("Group must be reverse-DNS format (e.g., platform.company.io)")

        if not request.version:
            errors.append("Version is required")
        elif not re.match(r'^v[0-9]+alpha[0-9]+$', request.version):
            errors.append("Version must be like v1alpha1, v1beta1, etc.")

        if not request.spec_properties:
            errors.append("At least one spec property is required")

        return errors

    def enhance_request(self, request: CodegenRequest) -> CodegenRequest:
        """
        Enhance a request with additional metadata and defaults.

        Args:
            request: The base request to enhance

        Returns:
            CodegenRequest: Enhanced request with additional metadata
        """
        # Generate reasonable output directory if not set
        if not request.output_dir or request.output_dir == "/tmp/generated":
            request.output_dir = f"/tmp/{request.kind.lower()}"

        # Add description if not present
        if not request.description:
            request.description = f"Kubernetes {request.kind} API for platform extensions"

        return request