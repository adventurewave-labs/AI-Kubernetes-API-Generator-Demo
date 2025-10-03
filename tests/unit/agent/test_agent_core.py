"""
Unit tests for the AI scaffolding agent core functionality.
Tests the main agent logic that translates natural language to codegen commands.
"""

import pytest
import json
import subprocess
from unittest.mock import Mock, patch, call
from pathlib import Path

# Import the agent modules (we'll need to create these based on PLANS.md)
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from agent.agent_core import AgentCore, SystemPromptBuilder, CommandExecutor
from agent.exceptions import (
    AgentError,
    OpenAIAPIError,
    CommandExecutionError,
    InvalidResponseError
)


class TestSystemPromptBuilder:
    """Test the system prompt builder functionality."""

    def test_build_system_prompt_default_values(self):
        """Test building system prompt with default values."""
        builder = SystemPromptBuilder()
        prompt = builder.build()

        assert "Kubernetes Platform Engineering assistant" in prompt
        assert "openapi-mcp-codegen" in prompt
        assert "platform.cnoe.io" in prompt
        assert "v1alpha1" in prompt
        assert "single, minified JSON object" in prompt

    def test_build_system_prompt_custom_defaults(self):
        """Test building system prompt with custom default values."""
        builder = SystemPromptBuilder(
            default_group="custom.example.io",
            default_version="v1beta1"
        )
        prompt = builder.build()

        assert "custom.example.io" in prompt
        assert "v1beta1" in prompt
        assert "platform.cnoe.io" not in prompt

    def test_add_examples_to_prompt(self):
        """Test adding examples to the system prompt."""
        builder = SystemPromptBuilder()
        builder.add_example(
            user_input="Create a Database API",
            expected_output='{"command": ["test"]}'
        )
        prompt = builder.build()

        assert "Create a Database API" in prompt
        assert '{"command": ["test"]}' in prompt

    def test_validate_prompt_structure(self):
        """Test that the prompt has the required structure."""
        builder = SystemPromptBuilder()
        prompt = builder.build()

        # Check for required sections
        required_sections = [
            "role",
            "parse their request",
            "group",
            "version",
            "kind",
            "spec properties",
            "format your response",
            "JSON object"
        ]

        for section in required_sections:
            assert section.lower() in prompt.lower()


class TestAgentCore:
    """Test the core agent functionality."""

    @pytest.fixture
    def agent_core(self, mock_openai_client):
        """Create an AgentCore instance with mocked dependencies."""
        return AgentCore(
            openai_client=mock_openai_client,
            model="gpt-4",
            temperature=0.1,
            max_tokens=1000
        )

    def test_agent_initialization(self, agent_core):
        """Test agent initialization with parameters."""
        assert agent_core.model == "gpt-4"
        assert agent_core.temperature == 0.1
        assert agent_core.max_tokens == 1000
        assert agent_core.openai_client is not None

    def test_process_simple_request(self, agent_core, sample_natural_language_requests):
        """Test processing a simple natural language request."""
        request_data = sample_natural_language_requests["simple_vector_db"]
        result = agent_core.process_request(request_data["input"])

        assert "command" in result
        assert isinstance(result["command"], list)
        assert "openapi-mcp-codegen" in result["command"]
        assert "--output-dir" in result["command"]
        assert "--input-spec" in result["command"]

    def test_process_complex_request(self, agent_core, sample_natural_language_requests):
        """Test processing a complex natural language request."""
        request_data = sample_natural_language_requests["notebook_crd"]
        result = agent_core.process_request(request_data["input"])

        # Verify the command structure
        assert "command" in result
        command = result["command"]

        # Extract the JSON spec from the command
        spec_index = command.index("--input-spec") + 1
        spec_json = command[spec_index]
        spec_data = json.loads(spec_json)

        # Verify spec structure
        assert spec_data["group"] == request_data["expected_group"]
        assert spec_data["version"] == request_data["expected_version"]
        assert spec_data["kind"] == request_data["expected_kind"]

    def test_process_request_with_invalid_json_response(self, agent_core):
        """Test handling invalid JSON response from OpenAI."""
        # Mock invalid JSON response
        agent_core.openai_client.chat.completions.create.return_value.choices[0].message.content = "invalid json"

        with pytest.raises(InvalidResponseError) as exc_info:
            agent_core.process_request("test request")

        assert "Error parsing LLM response" in str(exc_info.value)

    def test_process_request_with_missing_command(self, agent_core):
        """Test handling response with missing command field."""
        # Mock response without command field
        agent_core.openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
            "response": "No command here"
        })

        with pytest.raises(InvalidResponseError) as exc_info:
            agent_core.process_request("test request")

        assert "Missing command field" in str(exc_info.value)

    def test_process_request_with_openai_error(self, agent_core):
        """Test handling OpenAI API errors."""
        # Mock OpenAI API error
        agent_core.openai_client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(OpenAIAPIError) as exc_info:
            agent_core.process_request("test request")

        assert "Error communicating with OpenAI API" in str(exc_info.value)

    def test_extract_api_spec_from_command(self, agent_core):
        """Test extracting API specification from generated command."""
        command = [
            "openapi-mcp-codegen",
            "--output-dir", "/tmp/test",
            "--go-header-file", "hack/boilerplate.go.txt",
            "--input-spec", '{"group":"test.io","version":"v1","kind":"Test","spec":{"properties":{"name":{"type":"string"}}}}'
        ]

        spec = agent_core._extract_api_spec(command)
        assert spec["group"] == "test.io"
        assert spec["version"] == "v1"
        assert spec["kind"] == "Test"
        assert "name" in spec["spec"]["properties"]

    def test_validate_api_spec_structure(self, agent_core):
        """Test API specification validation."""
        valid_spec = {
            "group": "test.io",
            "version": "v1alpha1",
            "kind": "TestResource",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

        assert agent_core._validate_api_spec(valid_spec) is True

    def test_validate_invalid_api_spec(self, agent_core):
        """Test validation of invalid API specifications."""
        invalid_specs = [
            {},  # Empty spec
            {"group": "test.io"},  # Missing required fields
            {"group": "test.io", "version": "v1", "kind": "Test"},  # Missing spec
            {"group": "test.io", "version": "v1", "kind": "Test", "spec": "invalid"},  # Invalid spec type
        ]

        for spec in invalid_specs:
            assert agent_core._validate_api_spec(spec) is False

    def test_infer_field_types_from_natural_language(self, agent_core):
        """Test inferring field types from natural language descriptions."""
        test_cases = [
            ("string field", {"type": "string"}),
            ("integer number", {"type": "integer"}),
            ("boolean flag", {"type": "boolean"}),
            ("array of strings", {"type": "array", "items": {"type": "string"}}),
            ("object with properties", {"type": "object"}),
        ]

        for description, expected_type in test_cases:
            inferred_type = agent_core._infer_field_type(description)
            assert inferred_type == expected_type

    @pytest.mark.parametrize("temperature", [0.0, 0.5, 1.0])
    def test_different_temperature_settings(self, mock_openai_client, temperature):
        """Test agent behavior with different temperature settings."""
        agent = AgentCore(
            openai_client=mock_openai_client,
            temperature=temperature
        )
        agent.process_request("test request")

        # Verify the temperature was passed to OpenAI
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["temperature"] == temperature


class TestCommandExecutor:
    """Test the command execution functionality."""

    @pytest.fixture
    def command_executor(self, mock_subprocess_run):
        """Create a CommandExecutor instance with mocked subprocess."""
        return CommandExecutor(
            codegen_binary_path="/usr/local/bin/openapi-mcp-codegen",
            default_boilerplate="hack/boilerplate.go.txt",
            default_output_dir="/tmp/test-output"
        )

    def test_execute_valid_command(self, command_executor, mock_subprocess_run):
        """Test executing a valid codegen command."""
        command = [
            "openapi-mcp-codegen",
            "--output-dir", "/tmp/test",
            "--go-header-file", "hack/boilerplate.go.txt",
            "--input-spec", '{"group":"test.io","version":"v1","kind":"Test","spec":{}}'
        ]

        result = command_executor.execute(command)

        assert result["success"] is True
        assert "output_dir" in result
        mock_subprocess_run.assert_called_once()

    def test_execute_command_with_subprocess_error(self, command_executor, mock_subprocess_run):
        """Test handling subprocess execution errors."""
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "openapi-mcp-codegen")

        command = ["openapi-mcp-codegen", "--invalid"]

        with pytest.raises(CommandExecutionError) as exc_info:
            command_executor.execute(command)

        assert "Error executing codegen command" in str(exc_info.value)

    def test_execute_command_with_binary_not_found(self, command_executor, mock_subprocess_run):
        """Test handling when codegen binary is not found."""
        mock_subprocess_run.side_effect = FileNotFoundError()

        command = ["openapi-mcp-codegen", "--test"]

        with pytest.raises(CommandExecutionError) as exc_info:
            command_executor.execute(command)

        assert "openapi-mcp-codegen not found" in str(exc_info.value)

    def test_prepare_command_paths(self, command_executor):
        """Test preparation of command with correct paths."""
        input_command = [
            "openapi-mcp-codegen",
            "--output-dir", "relative/path",
            "--go-header-file", "relative/boilerplate.txt",
            "--input-spec", '{"group":"test.io"}'
        ]

        prepared_command = command_executor._prepare_command_paths(input_command)

        # Verify paths are made absolute
        assert "/tmp/test-output" in prepared_command
        assert "hack/boilerplate.go.txt" in prepared_command

    def test_validate_command_structure(self, command_executor):
        """Test validation of command structure."""
        valid_command = [
            "openapi-mcp-codegen",
            "--output-dir", "/tmp/test",
            "--go-header-file", "boilerplate.txt",
            "--input-spec", '{"group":"test.io"}'
        ]

        invalid_commands = [
            [],  # Empty command
            ["openapi-mcp-codegen"],  # Missing arguments
            ["wrong-binary"],  # Wrong binary
            ["openapi-mcp-codegen", "--output-dir"],  # Missing value
        ]

        assert command_executor._validate_command(valid_command) is True

        for invalid_cmd in invalid_commands:
            assert command_executor._validate_command(invalid_cmd) is False

    def test_extract_output_directory_from_command(self, command_executor):
        """Test extracting output directory from command."""
        command = [
            "openapi-mcp-codegen",
            "--output-dir", "/tmp/test-output",
            "--go-header-file", "boilerplate.txt"
        ]

        output_dir = command_executor._extract_output_dir(command)
        assert output_dir == "/tmp/test-output"

    def test_execute_with_custom_working_directory(self, command_executor, mock_subprocess_run, temp_dir):
        """Test executing command with custom working directory."""
        command = ["openapi-mcp-codegen", "--test"]

        result = command_executor.execute(command, working_dir=str(temp_dir))

        assert result["success"] is True
        mock_subprocess_run.assert_called_once()

        # Verify working directory was set
        call_kwargs = mock_subprocess_run.call_args[1]
        assert "cwd" in call_kwargs
        assert call_kwargs["cwd"] == str(temp_dir)


class TestAgentIntegration:
    """Integration tests for the complete agent workflow."""

    def test_end_to_end_request_processing(self, mock_openai_client, mock_subprocess_run):
        """Test complete end-to-end request processing."""
        agent = AgentCore(openai_client=mock_openai_client)
        executor = CommandExecutor()

        # Process natural language request
        request = "Create a Database API with engine and replicas fields"
        command_result = agent.process_request(request)

        # Execute the generated command
        execution_result = executor.execute(command_result["command"])

        assert execution_result["success"] is True
        assert "output_dir" in execution_result

    def test_error_recovery_workflow(self, mock_openai_client):
        """Test error recovery in the agent workflow."""
        # First call fails, second succeeds
        mock_openai_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            Mock(choices=[Mock(message=Mock(content=json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })))])
        ]

        agent = AgentCore(openai_client=mock_openai_client, max_retries=2)

        # Should succeed after retry
        result = agent.process_request("test request")
        assert "command" in result

    def test_request_caching(self, mock_openai_client):
        """Test that identical requests are cached appropriately."""
        agent = AgentCore(openai_client=mock_openai_client, enable_cache=True)

        request = "Create a simple API with name field"

        # First call
        result1 = agent.process_request(request)

        # Second call with same request
        result2 = agent.process_request(request)

        # Results should be identical
        assert result1 == result2

        # OpenAI should only be called once due to caching
        assert mock_openai_client.chat.completions.create.call_count == 1

    @pytest.mark.parametrize("request_input", [
        "Create a VectorDB API with engine_type string and replicas integer",
        "I need a Notebook CRD with cpu and memory string fields",
        "Make a ClusterClaim API with clusterId string field"
    ])
    def test_various_request_patterns(self, mock_openai_client, request_input):
        """Test various patterns of natural language requests."""
        agent = AgentCore(openai_client=mock_openai_client)

        result = agent.process_request(request_input)

        assert "command" in result
        assert isinstance(result["command"], list)
        assert len(result["command"]) > 0