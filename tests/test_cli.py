"""
Tests for the CLI module
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from src.ai_platform_generator.cli import main
from src.ai_platform_generator.agent import CodegenRequest


class TestCLI:
    """Test cases for CLI commands"""

    def setup_method(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.api_key = "test-api-key"

    def test_main_command_exists(self):
        """Test that main command is available"""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "AI-Assisted Platform Extension Generator" in result.output

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    @patch('src.ai_platform_generator.cli.CodeGenerator')
    @patch('src.ai_platform_generator.cli.Prompt.ask')
    def test_interactive_command_success(self, mock_prompt, mock_generator, mock_agent):
        """Test interactive command successful flow"""
        # Mock agent
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        mock_request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec_properties={"name": {"type": "string"}},
            output_dir="/tmp/testresource",
            description="Test resource"
        )
        mock_agent_instance.parse_request.return_value = mock_request
        mock_agent_instance.validate_request.return_value = []
        mock_agent_instance.enhance_request.return_value = mock_request

        # Mock generator
        mock_generator_instance = Mock()
        mock_generator.return_value = mock_generator_instance

        mock_result = Mock()
        mock_result.success = True
        mock_result.output_path = "/tmp/testresource"
        mock_result.generated_files = ["/tmp/testresource/main.go"]
        mock_generator_instance.generate_kubernetes_controller.return_value = mock_result

        # Mock user input
        mock_prompt.side_effect = ["Create a TestResource with name field", "exit"]

        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
            result = self.runner.invoke(main, ['interactive'])

        assert result.exit_code == 0
        mock_agent_instance.parse_request.assert_called()
        mock_generator_instance.generate_kubernetes_controller.assert_called()

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    def test_interactive_command_no_api_key(self, mock_agent):
        """Test interactive command without API key"""
        mock_agent.side_effect = ValueError("OPENROUTER_API_KEY environment variable is required")

        result = self.runner.invoke(main, ['interactive'])

        assert result.exit_code == 1
        assert "Failed to initialize" in result.output

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    def test_generate_command_success(self, mock_agent):
        """Test generate command success"""
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        mock_request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec_properties={"name": {"type": "string"}},
            output_dir="/tmp/testresource",
            description="Test resource"
        )
        mock_agent_instance.parse_request.return_value = mock_request
        mock_agent_instance.validate_request.return_value = []
        mock_agent_instance.enhance_request.return_value = mock_request

        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
            result = self.runner.invoke(main, [
                'generate',
                'Create a TestResource with name field',
                '--format', 'json'
            ])

        assert result.exit_code == 0
        mock_agent_instance.parse_request.assert_called_with("Create a TestResource with name field")

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    def test_generate_command_validation_error(self, mock_agent):
        """Test generate command with validation errors"""
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        mock_agent_instance.parse_request.return_value = Mock()
        mock_agent_instance.validate_request.return_value = ["Invalid kind format"]
        mock_agent_instance.enhance_request.return_value = Mock()

        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
            result = self.runner.invoke(main, [
                'generate',
                'invalid request'
            ])

        assert result.exit_code == 1
        assert "Validation errors" in result.output

    def test_build_command_success(self):
        """Test build command success"""
        # Create a temporary request file
        request_data = {
            "group": "platform.test.io",
            "version": "v1alpha1",
            "kind": "TestResource",
            "spec_properties": {"name": {"type": "string"}},
            "output_dir": "/tmp/test",
            "description": "Test resource"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(request_data, f)
            temp_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = self.runner.invoke(main, [
                    'build',
                    temp_file,
                    '--output-dir', temp_dir
                ])

                assert result.exit_code == 0
                assert "Build completed successfully" in result.output

                # Check that files were created
                output_path = Path(temp_dir)
                assert (output_path / "main.go").exists()
                assert (output_path / "go.mod").exists()

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_build_command_file_not_found(self):
        """Test build command with non-existent file"""
        result = self.runner.invoke(main, [
            'build',
            '/nonexistent/file.json'
        ])

        assert result.exit_code == 2  # Click file not found error

    def test_build_command_invalid_json(self):
        """Test build command with invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name

        try:
            result = self.runner.invoke(main, [
                'build',
                temp_file
            ])

            assert result.exit_code == 1
            assert "Error" in result.output

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_examples_command(self):
        """Test examples command"""
        result = self.runner.invoke(main, ['examples'])

        assert result.exit_code == 0
        assert "Example Requests" in result.output
        assert "VectorDB" in result.output
        assert "CacheCluster" in result.output
        assert "DatabaseBackup" in result.output

    def test_generate_command_yaml_format(self):
        """Test generate command with YAML output format"""
        with patch('src.ai_platform_generator.cli.PlatformExtensionAgent') as mock_agent:
            mock_agent_instance = Mock()
            mock_agent.return_value = mock_agent_instance

            mock_request = CodegenRequest(
                group="platform.test.io",
                version="v1alpha1",
                kind="TestResource",
                spec_properties={"name": {"type": "string"}},
                output_dir="/tmp/testresource",
                description="Test resource"
            )
            mock_agent_instance.parse_request.return_value = mock_request
            mock_agent_instance.validate_request.return_value = []
            mock_agent_instance.enhance_request.return_value = mock_request

            with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
                result = self.runner.invoke(main, [
                    'generate',
                    'Create a TestResource',
                    '--format', 'yaml'
                ])

            assert result.exit_code == 0
            assert "Kind: TestResource" in result.output
            assert "Group: platform.test.io" in result.output

    def test_generate_command_custom_output_dir(self):
        """Test generate command with custom output directory"""
        with patch('src.ai_platform_generator.cli.PlatformExtensionAgent') as mock_agent:
            mock_agent_instance = Mock()
            mock_agent.return_value = mock_agent_instance

            mock_request = CodegenRequest(
                group="platform.test.io",
                version="v1alpha1",
                kind="TestResource",
                spec_properties={"name": {"type": "string"}},
                output_dir="/tmp/testresource",
                description="Test resource"
            )
            mock_agent_instance.parse_request.return_value = mock_request
            mock_agent_instance.validate_request.return_value = []
            mock_agent_instance.enhance_request.return_value = mock_request

            with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
                result = self.runner.invoke(main, [
                    'generate',
                    'Create a TestResource',
                    '--output-dir', '/custom/output'
                ])

            assert result.exit_code == 0
            # Check that the output directory was overridden
            assert mock_agent_instance.enhance_request.called

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    def test_interactive_command_keyboard_interrupt(self, mock_agent, mock_prompt):
        """Test interactive command handles keyboard interrupt"""
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        mock_request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec_properties={"name": {"type": "string"}},
            output_dir="/tmp/testresource",
            description="Test resource"
        )
        mock_agent_instance.parse_request.return_value = mock_request
        mock_agent_instance.validate_request.return_value = []
        mock_agent_instance.enhance_request.return_value = mock_request

        # Mock keyboard interrupt on first prompt
        mock_prompt.side_effect = KeyboardInterrupt()

        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
            result = self.runner.invoke(main, ['interactive'])

        # Should not crash, just return to prompt
        assert "Operation cancelled" in result.output

    @patch('src.ai_platform_generator.cli.PlatformExtensionAgent')
    def test_generate_command_custom_model(self, mock_agent):
        """Test generate command with custom model"""
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        mock_request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec_properties={"name": {"type": "string"}},
            output_dir="/tmp/testresource",
            description="Test resource"
        )
        mock_agent_instance.parse_request.return_value = mock_request
        mock_agent_instance.validate_request.return_value = []
        mock_agent_instance.enhance_request.return_value = mock_request

        with patch.dict('os.environ', {'OPENROUTER_API_KEY': self.api_key}):
            result = self.runner.invoke(main, [
                'generate',
                'Create a TestResource',
                '--model', 'gpt-4'
            ])

        assert result.exit_code == 0
        # Check that agent was initialized with custom model
        mock_agent.assert_called_with(api_key=self.api_key, model='gpt-4')