"""
Command Line Interface for AI Platform Extension Generator

This module provides the CLI interface for interacting with the AI agent.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.tree import Tree
from rich import print as rprint

from .agent import PlatformExtensionAgent, CodegenRequest
from .codegen import CodeGenerator, GenerationResult


console = Console()


@click.group()
@click.version_option()
def main():
    """AI-Assisted Platform Extension Generator

    Generate Kubernetes platform extensions through natural language.
    """
    pass


@main.command()
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='OpenRouter API key')
@click.option('--model', default='anthropic/claude-3.5-sonnet', help='AI model to use')
@click.option('--output-dir', default='./generated', help='Output directory for generated code')
def interactive(api_key: Optional[str], model: str, output_dir: str):
    """Start interactive mode for generating platform extensions."""

    try:
        agent = PlatformExtensionAgent(api_key=api_key, model=model)
        generator = CodeGenerator()

        console.print(Panel.fit(
            "[bold blue]AI Platform Extension Generator[/bold blue]\n\n"
            "Describe the Kubernetes API you want to create in natural language.\n"
            "Examples:\n"
            "• \"Create a VectorDB API with engine_type and replicas\"\n"
            "• \"I need a CacheCluster with size and memory fields\"\n"
            "• \"Build a DatabaseBackup resource with schedule and retention\"",
            title="Welcome"
        ))

        while True:
            try:
                user_input = Prompt.ask(
                    "\n[bold green]Describe the Kubernetes API you want to create[/bold green]",
                    default="exit"
                )

                if user_input.lower() in ['exit', 'quit', 'q']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Parse the request
                with console.status("[bold green]🤔 Thinking...[/bold green]"):
                    request = agent.parse_request(user_input)
                    request = agent.enhance_request(request)

                    # Override output directory if specified
                    if output_dir != './generated':
                        request.output_dir = output_dir

                # Validate the request
                errors = agent.validate_request(request)
                if errors:
                    console.print("[red]❌ Validation errors:[/red]")
                    for error in errors:
                        console.print(f"  • {error}")
                    continue

                # Display parsed request
                console.print(Panel.fit(
                    f"[bold]Parsed Request:[/bold]\n"
                    f"Kind: {request.kind}\n"
                    f"Group: {request.group}\n"
                    f"Version: {request.version}\n"
                    f"Spec Properties: {len(request.spec_properties)} fields\n"
                    f"Output: {request.output_dir}",
                    title="✅ Request Parsed"
                ))

                # Generate code
                with console.status("[bold green]🔧 Generating code...[/bold green]"):
                    result = generator.generate_kubernetes_controller(request)

                if result.success:
                    console.print("[green]✅ Code generated successfully![/green]")
                    console.print(f"[blue]📁 Output directory: {result.output_path}[/blue]")

                    # Show generated files
                    if result.generated_files:
                        tree = Tree("📂 Generated Files")
                        for file_path in result.generated_files:
                            rel_path = Path(file_path).relative_to(result.output_path)
                            tree.add(f"📄 {rel_path}")
                        console.print(tree)

                    # Show next steps
                    console.print(Panel.fit(
                        f"[bold]Next Steps:[/bold]\n"
                        f"1. cd {result.output_path}\n"
                        f"2. go mod tidy\n"
                        f"3. docker build -t {request.kind.lower()}-controller .\n"
                        f"4. kubectl apply -f config/\n"
                        f"\n[bold]Testing:[/bold]\n"
                        f"• go test ./...\n"
                        f"• make docker-build docker-run",
                        title="🚀 Ready to Deploy"
                    ))
                else:
                    console.print("[red]❌ Code generation failed[/red]")
                    console.print(f"[red]Error: {result.stderr}[/red]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    except Exception as e:
        console.print(f"[red]Failed to initialize: {e}[/red]")
        sys.exit(1)


@main.command()
@click.argument('description')
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='OpenRouter API key')
@click.option('--model', default='anthropic/claude-3.5-sonnet', help='AI model to use')
@click.option('--output-dir', help='Output directory for generated code')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml']), default='json', help='Output format')
def generate(description: str, api_key: Optional[str], model: str, output_dir: Optional[str], output_format: str):
    """Generate a platform extension from a description.

    DESCRIPTION: Natural language description of the Kubernetes API you want to create.
    """

    try:
        agent = PlatformExtensionAgent(api_key=api_key, model=model)

        console.print(f"[green]🤖 Processing request: {description}[/green]")

        # Parse the request
        with console.status("[bold green]🔍 Analyzing description...[/bold green]"):
            request = agent.parse_request(description)
            request = agent.enhance_request(request)

            if output_dir:
                request.output_dir = output_dir

        # Validate the request
        errors = agent.validate_request(request)
        if errors:
            console.print("[red]❌ Validation errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            sys.exit(1)

        # Output the parsed request
        if output_format == 'json':
            output = {
                "kind": request.kind,
                "group": request.group,
                "version": request.version,
                "spec_properties": request.spec_properties,
                "output_dir": request.output_dir,
                "description": request.description
            }
            console.print(json.dumps(output, indent=2))
        else:
            console.print(f"Kind: {request.kind}")
            console.print(f"Group: {request.group}")
            console.print(f"Version: {request.version}")
            console.print(f"Output Directory: {request.output_dir}")
            console.print(f"Description: {request.description}")
            console.print("Spec Properties:")
            for prop, info in request.spec_properties.items():
                console.print(f"  {prop}: {info.get('type', 'string')}")

        console.print(f"\n[green]✅ Request parsed successfully![/green]")
        console.print(f"[blue]Run with --output-dir to generate code.[/blue]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.argument('request_file', type=click.Path(exists=True))
@click.option('--output-dir', help='Override output directory')
def build(request_file: str, output_dir: Optional[str]):
    """Build code from a JSON request file.

    REQUEST_FILE: Path to JSON file containing the parsed request.
    """

    try:
        with open(request_file, 'r') as f:
            request_data = json.load(f)

        request = CodegenRequest(**request_data)
        if output_dir:
            request.output_dir = output_dir

        generator = CodeGenerator()

        console.print(f"[green]🔧 Building {request.kind} controller...[/green]")

        with console.status("[bold green]⚙️ Generating files...[/bold green]"):
            result = generator.generate_kubernetes_controller(request)

        if result.success:
            console.print("[green]✅ Build completed successfully![/green]")
            console.print(f"[blue]📁 Output: {result.output_path}[/blue]")

            if result.generated_files:
                tree = Tree("📂 Generated Files")
                for file_path in result.generated_files:
                    rel_path = Path(file_path).relative_to(result.output_path)
                    tree.add(f"📄 {rel_path}")
                console.print(tree)
        else:
            console.print("[red]❌ Build failed[/red]")
            console.print(f"[red]Error: {result.stderr}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command()
def examples():
    """Show example requests."""

    examples = [
        {
            "description": "Create a VectorDB API for AI workloads",
            "request": "I need a VectorDB API with engine_type (string) and replicas (integer) fields"
        },
        {
            "description": "Create a CacheCluster for caching",
            "request": "Build a CacheCluster with size (string), memory (string), and port (integer) fields"
        },
        {
            "description": "Create a DatabaseBackup resource",
            "request": "I need a DatabaseBackup with schedule (string), retention_days (integer), and enabled (boolean)"
        },
        {
            "description": "Create a ConfigMap template",
            "request": "Make a ConfigTemplate with template_name (string), variables (object), and namespace (string)"
        }
    ]

    console.print(Panel.fit(
        "[bold blue]Example Requests[/bold blue]\n\n"
        "You can use these descriptions to generate different types of Kubernetes APIs:",
        title="📚 Examples"
    ))

    for i, example in enumerate(examples, 1):
        console.print(f"\n[bold]{i}. {example['description']}[/bold]")
        console.print(f"[dim]Request: {example['request']}[/dim]")


if __name__ == '__main__':
    main()