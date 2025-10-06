#!/bin/bash

# =============================================================================
# AI-Assisted Platform Extension Generator - Comprehensive Run Script
# =============================================================================
# This script sets up the complete environment and runs the AI scaffolding agent
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project Configuration
PROJECT_NAME="AI-Assisted Platform Extension Generator"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MIN_VERSION="3.8"

# =============================================================================
# ENVIRONMENT VARIABLES & API KEYS
# =============================================================================

echo -e "${CYAN}🔧 Setting up environment variables...${NC}"

# OpenAI API Configuration (REQUIRED for AI functionality)
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"

# Alternative AI Providers (Optional)
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-}"
export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"

# OpenRouter API Configuration (ALTERNATIVE TO OPENAI)
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-deepseek/deepseek-chat-v3.1:free}"

# Project Environment Variables
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH}"
export AI_AGENT_LOG_LEVEL="${AI_AGENT_LOG_LEVEL:-INFO}"
export AI_AGENT_OUTPUT_DIR="${AI_AGENT_OUTPUT_DIR:-${PROJECT_DIR}/generated}"
export AI_AGENT_CONFIG_FILE="${AI_AGENT_CONFIG_FILE:-${PROJECT_DIR}/config/agent_config.yaml}"

# Development Settings
export AI_AGENT_DEBUG="${AI_AGENT_DEBUG:-false}"
export AI_AGENT_MOCK_MODE="${AI_AGENT_MOCK_MODE:-false}"

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

validate_python_version() {
    echo -e "${BLUE}🐍 Validating Python version...${NC}"

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is required but not installed. Please install Python 3.8+${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    REQUIRED_VERSION="3.8"

    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        echo -e "${GREEN}✅ Python ${PYTHON_VERSION} detected${NC}"
    else
        echo -e "${RED}❌ Python ${PYTHON_VERSION} is too old. Minimum required: ${REQUIRED_VERSION}${NC}"
        exit 1
    fi
}

validate_api_key() {
    echo -e "${BLUE}🔑 Validating API keys...${NC}"

    # Check for any supported API key
    if [[ -n "$OPENAI_API_KEY" ]]; then
        echo -e "${GREEN}✅ OpenAI API key is set${NC}"
        return 0
    elif [[ -n "$OPENROUTER_API_KEY" ]]; then
        echo -e "${GREEN}✅ OpenRouter API key is set${NC}"
        echo -e "${GREEN}   Using model: ${OPENROUTER_MODEL:-anthropic/claude-3.5-sonnet}${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  WARNING: No API key found${NC}"
        echo -e "${YELLOW}   The AI agent requires an API key to function${NC}"
        echo -e "${YELLOW}   Please set one of the following:${NC}"
        echo -e "${YELLOW}     - OpenAI:     export OPENAI_API_KEY='your-key-here'${NC}"
        echo -e "${YELLOW}     - OpenRouter: export OPENROUTER_API_KEY='your-key-here'${NC}"

        read -p "Do you want to continue without API key? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}❌ Exiting. Please set an API key and try again${NC}"
            exit 1
        fi
    fi
}

validate_project_structure() {
    echo -e "${BLUE}📁 Validating project structure...${NC}"

    local required_dirs=("src" "tests" "examples" "config")
    local required_files=("src/agent.py" "requirements.txt" "examples/demo.py")

    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$PROJECT_DIR/$dir" ]]; then
            echo -e "${RED}❌ Required directory not found: $dir${NC}"
            exit 1
        fi
    done

    for file in "${required_files[@]}"; do
        if [[ ! -f "$PROJECT_DIR/$file" ]]; then
            echo -e "${RED}❌ Required file not found: $file${NC}"
            exit 1
        fi
    done

    echo -e "${GREEN}✅ Project structure is valid${NC}"
}

# =============================================================================
# SETUP FUNCTIONS
# =============================================================================

setup_python_environment() {
    echo -e "${CYAN}🏗️  Setting up Python environment...${NC}"

    # Create virtual environment if it doesn't exist
    if [[ ! -d "$PROJECT_DIR/venv" ]]; then
        echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
        python3 -m venv "$PROJECT_DIR/venv"
    fi

    # Activate virtual environment
    echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
    source "$PROJECT_DIR/venv/bin/activate"

    # Upgrade pip
    echo -e "${YELLOW}⬆️  Upgrading pip...${NC}"
    pip install --upgrade pip

    # Install requirements
    echo -e "${YELLOW}📥 Installing Python dependencies...${NC}"
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        pip install -r "$PROJECT_DIR/requirements.txt"
    else
        echo -e "${RED}❌ requirements.txt not found${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Python environment setup complete${NC}"
}

setup_project_directories() {
    echo -e "${CYAN}📂 Creating project directories...${NC}"

    local directories=(
        "generated"
        "generated/openapi-specs"
        "generated/mcp-configs"
        "logs"
        "temp"
    )

    for dir in "${directories[@]}"; do
        mkdir -p "$PROJECT_DIR/$dir"
    done

    echo -e "${GREEN}✅ Project directories created${NC}"
}

create_agent_config() {
    echo -e "${CYAN}⚙️  Creating agent configuration...${NC}"

    local config_dir="$PROJECT_DIR/config"
    local config_file="$config_dir/agent_config.yaml"

    mkdir -p "$config_dir"

    cat > "$config_file" << 'EOF'
# AI-Assisted Platform Extension Generator Configuration
agent:
  name: "AI Scaffolding Agent"
  version: "1.0.0"
  description: "Generates OpenAPI specifications from natural language"

openai:
  model: "gpt-4"
  max_tokens: 4000
  temperature: 0.1
  timeout: 60

output:
  format: "yaml"
  indent: 2
  validate_schemas: true

kubernetes:
  api_version: "v1"
  kind_base: "CustomResourceDefinition"
  group_pattern: "*.platform.cnoe.io"
  version_pattern: "v1alpha1"

logging:
  level: "INFO"
  format: "json"
  file: "logs/agent.log"

validation:
  strict_mode: true
  require_descriptions: true
  enforce_naming: true
EOF

    echo -e "${GREEN}✅ Agent configuration created at $config_file${NC}"
}

# =============================================================================
# RUN FUNCTIONS
# =============================================================================

run_demo() {
    echo -e "${PURPLE}🚀 Running AI-Powered Demo Application...${NC}"

    cd "$PROJECT_DIR"
    python3 examples/ai_demo.py

    echo -e "${GREEN}✅ AI Demo completed successfully${NC}"
}

run_interactive_mode() {
    echo -e "${PURPLE}💬 Starting Interactive Mode...${NC}"
    echo -e "${CYAN}Enter your API description (or 'quit' to exit):${NC}"

    cd "$PROJECT_DIR"

    while true; do
        echo -e "${YELLOW}API Description:${NC}"
        read -p "> " user_input

        if [[ "$user_input" == "quit" || "$user_input" == "exit" ]]; then
            echo -e "${GREEN}👋 Goodbye!${NC}"
            break
        fi

        if [[ -z "$user_input" ]]; then
            echo -e "${YELLOW}Please enter a description or 'quit' to exit${NC}"
            continue
        fi

        # Process the input with the agent
        python3 -c "
import sys
import os
sys.path.insert(0, 'src')
from agent import AIScaffoldingAgent

try:
    agent = AIScaffoldingAgent()
    result = agent.generate_from_description('$user_input')
    print('\n🎉 Generated OpenAPI Specification:')
    print('=' * 50)
    print(result)
    print('=' * 50)
except Exception as e:
    print(f'❌ Error: {e}')
    print('Please check your API key and try again.')
"

        echo
    done
}

run_tests() {
    echo -e "${PURPLE}🧪 Running Test Suite...${NC}"

    cd "$PROJECT_DIR"

    # Check if pytest is installed
    if ! command -v pytest &> /dev/null; then
        echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
        pip install pytest pytest-mock
    fi

    pytest tests/ -v

    echo -e "${GREEN}✅ Tests completed${NC}"
}

show_help() {
    cat << EOF
${CYAN}AI-Assisted Platform Extension Generator - Run Script${NC}

${YELLOW}Usage:${NC}
    $0 [COMMAND] [OPTIONS]

${YELLOW}Commands:${NC}
    demo        Run the demo application with examples
    interactive Start interactive mode for custom API generation
    test        Run the test suite
    setup       Set up the environment only (don't run anything)
    help        Show this help message

${YELLOW}Environment Variables:${NC}
    OPENAI_API_KEY         Your OpenAI API key (REQUIRED)
    OPENAI_MODEL           OpenAI model to use (default: gpt-4)
    AI_AGENT_DEBUG         Enable debug mode (default: false)
    AI_AGENT_MOCK_MODE     Use mock responses for testing (default: false)

${YELLOW}Examples:${NC}
    # Set API key and run demo
    export OPENAI_API_KEY='your-key-here'
    $0 demo

    # Interactive mode
    $0 interactive

    # Run tests
    $0 test

    # Setup only
    $0 setup

EOF
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    echo -e "${CYAN}🚀 ${PROJECT_NAME}${NC}"
    echo -e "${CYAN}======================================${NC}"
    echo

    # Parse command line arguments
    case "${1:-demo}" in
        "demo"|"run"|"start")
            COMMAND="demo"
            ;;
        "interactive"|"i"|"chat")
            COMMAND="interactive"
            ;;
        "test"|"t")
            COMMAND="test"
            ;;
        "setup"|"init")
            COMMAND="setup"
            ;;
        "help"|"-h"|"--help")
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $1${NC}"
            show_help
            exit 1
            ;;
    esac

    # Validation
    validate_python_version
    validate_project_structure

    # Setup
    setup_python_environment
    setup_project_directories
    create_agent_config

    # Validate API key for commands that need it
    if [[ "$COMMAND" == "demo" || "$COMMAND" == "interactive" ]]; then
        validate_api_key
    fi

    # Show environment summary
    echo
    echo -e "${GREEN}🎯 Environment Summary:${NC}"
    echo -e "   Project Directory: ${PROJECT_DIR}"
    echo -e "   Python Version: $(python3 --version)"
    echo -e "   Virtual Environment: ${PROJECT_DIR}/venv"
    echo -e "   OpenAI API Key: ${OPENAI_API_KEY:+SET}${OPENAI_API_KEY:-NOT_SET}"
    echo -e "   Output Directory: ${AI_AGENT_OUTPUT_DIR}"
    echo

    # Execute command
    case "$COMMAND" in
        "demo")
            run_demo
            ;;
        "interactive")
            run_interactive_mode
            ;;
        "test")
            run_tests
            ;;
        "setup")
            echo -e "${GREEN}✅ Setup completed successfully${NC}"
            echo -e "${CYAN}You can now run the application with: $0 demo${NC}"
            ;;
    esac

    echo
    echo -e "${GREEN}🎉 ${PROJECT_NAME} completed successfully!${NC}"
}

# Trap to ensure clean exit
trap 'echo -e "\n${YELLOW}🛑 Script interrupted. Cleaning up...${NC}"' INT TERM

# Run main function with all arguments
main "$@"