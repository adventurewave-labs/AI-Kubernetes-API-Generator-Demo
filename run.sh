#!/bin/bash

# =============================================================================
# AI Kubernetes API Generator - Comprehensive Run Script
# =============================================================================
# This script sets up the complete environment and runs the AI Kubernetes API generator
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
PROJECT_NAME="AI Kubernetes API Generator"
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
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-meta-llama/llama-3.2-3b-instruct:free}"

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

    # Install system dependencies if missing
    if ! command -v pip &> /dev/null; then
        echo -e "${YELLOW}📦 Installing system Python packages...${NC}"
        # Try different package managers
        if command -v apt &> /dev/null; then
            echo -e "${YELLOW}   Using apt to install python3-pip and python3-venv...${NC}"
            sudo apt update && sudo apt install -y python3-pip python3-venv
        elif command -v yum &> /dev/null; then
            echo -e "${YELLOW}   Using yum to install python3-pip...${NC}"
            sudo yum install -y python3-pip
        elif command -v brew &> /dev/null; then
            echo -e "${YELLOW}   Using brew to install python3...${NC}"
            brew install python3
        else
            echo -e "${RED}❌ Cannot install pip automatically. Please install python3-pip manually.${NC}"
            echo -e "${YELLOW}   On Ubuntu/Debian: sudo apt install python3-pip python3-venv${NC}"
            echo -e "${YELLOW}   On CentOS/RHEL: sudo yum install python3-pip${NC}"
            exit 1
        fi
    fi

    # Create virtual environment if it doesn't exist
    if [[ ! -d "$PROJECT_DIR/venv" ]]; then
        echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
        python3 -m venv "$PROJECT_DIR/venv"
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}❌ Failed to create virtual environment. Trying without venv...${NC}"
            echo -e "${YELLOW}🔄 Using system Python directly...${NC}"
            # Set up for system Python without venv
            export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH}"
            VENV_AVAILABLE=false
        else
            # Verify venv was created properly
            if [[ -f "$PROJECT_DIR/venv/bin/activate" ]]; then
                echo -e "${GREEN}✅ Virtual environment created successfully${NC}"
                VENV_AVAILABLE=true
            else
                echo -e "${RED}❌ Virtual environment creation incomplete. Using system Python...${NC}"
                echo -e "${YELLOW}🔄 Removing broken venv and using system Python directly...${NC}"
                rm -rf "$PROJECT_DIR/venv"
                export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH}"
                VENV_AVAILABLE=false
            fi
        fi
    else
        # Check if venv is complete
        if [[ -f "$PROJECT_DIR/venv/bin/activate" ]]; then
            VENV_AVAILABLE=true
        else
            echo -e "${YELLOW}⚠️  Incomplete virtual environment found. Recreating...${NC}"
            rm -rf "$PROJECT_DIR/venv"
            echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
            python3 -m venv "$PROJECT_DIR/venv"
            if [[ $? -ne 0 || ! -f "$PROJECT_DIR/venv/bin/activate" ]]; then
                echo -e "${RED}❌ Failed to create virtual environment. Using system Python...${NC}"
                export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH}"
                VENV_AVAILABLE=false
            else
                echo -e "${GREEN}✅ Virtual environment recreated successfully${NC}"
                VENV_AVAILABLE=true
            fi
        fi
    fi

    # Activate virtual environment if available
    if [[ "$VENV_AVAILABLE" == true ]]; then
        echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
        source "$PROJECT_DIR/venv/bin/activate"
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}❌ Failed to activate virtual environment. Using system Python...${NC}"
            export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH}"
            VENV_AVAILABLE=false
        else
            echo -e "${GREEN}✅ Virtual environment activated successfully${NC}"
        fi
    fi

    # Upgrade pip if in venv
    if [[ "$VENV_AVAILABLE" == true ]]; then
        echo -e "${YELLOW}⬆️  Upgrading pip...${NC}"
        pip install --upgrade pip
    fi

    # Install requirements
    echo -e "${YELLOW}📥 Installing Python dependencies...${NC}"
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        pip install -r "$PROJECT_DIR/requirements.txt"
    else
        echo -e "${YELLOW}📦 Installing core dependencies manually...${NC}"
        # Install core packages if requirements.txt doesn't exist
        pip install --upgrade pip
        pip install requests openpyxl pyyaml
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
# AI Kubernetes API Generator Configuration
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
    echo -e "${PURPLE}🚀 Running Complete AI Kubernetes API Demo...${NC}"

    cd "$PROJECT_DIR"

    # Step 1: Install kubectl if needed
    echo -e "${CYAN}🔧 Checking/Installing kubectl CLI...${NC}"
    if ! command -v kubectl &> /dev/null; then
        echo -e "${YELLOW}📦 Installing kubectl CLI automatically...${NC}"

        # Detect OS and architecture
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        ARCH=$(uname -m)
        case $ARCH in
            x86_64) ARCH="amd64" ;;
            aarch64|arm64) ARCH="arm64" ;;
            *)
                echo -e "${RED}❌ Unsupported architecture: $ARCH${NC}"
                return 1
                ;;
        esac

        # Download and install kubectl
        KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt)
        KUBECTL_URL="https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"

        echo -e "${CYAN}📥 Downloading kubectl ${KUBECTL_VERSION}...${NC}"

        # Create temp directory for download
        TEMP_DIR=$(mktemp -d)
        cd "$TEMP_DIR"

        # Download kubectl
        if curl -Lo ./kubectl "$KUBECTL_URL"; then
            chmod +x ./kubectl

            # Try to install to /usr/local/bin (requires sudo)
            if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
                echo -e "${CYAN}📦 Installing kubectl to /usr/local/bin...${NC}"
                sudo mv ./kubectl /usr/local/bin/kubectl
            else
                # Fallback: install to ~/.local/bin
                echo -e "${CYAN}📦 Installing kubectl to ~/.local/bin...${NC}"
                mkdir -p ~/.local/bin
                mv ./kubectl ~/.local/bin/kubectl

                # Add ~/.local/bin to PATH if not already there
                if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
                    export PATH="$HOME/.local/bin:$PATH"
                    echo -e "${YELLOW}ℹ️  Added ~/.local/bin to PATH. You may need to restart your shell.${NC}"
                fi
            fi

            echo -e "${GREEN}✅ kubectl installed successfully${NC}"
        else
            echo -e "${RED}❌ Failed to download kubectl${NC}"
            cd "$PROJECT_DIR"
            rm -rf "$TEMP_DIR"
            return 1
        fi

        # Cleanup
        cd "$PROJECT_DIR"
        rm -rf "$TEMP_DIR"
    else
        echo -e "${GREEN}✅ kubectl CLI already installed${NC}"
    fi

    # Step 2: Install kind if needed
    echo -e "${CYAN}🔧 Checking/Installing kind CLI...${NC}"
    if ! command -v kind &> /dev/null; then
        echo -e "${YELLOW}📦 Installing kind CLI automatically...${NC}"

        # Detect OS and architecture
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        ARCH=$(uname -m)
        case $ARCH in
            x86_64) ARCH="amd64" ;;
            aarch64|arm64) ARCH="arm64" ;;
            *)
                echo -e "${RED}❌ Unsupported architecture: $ARCH${NC}"
                return 1
                ;;
        esac

        # Download and install kind
        KIND_VERSION="v0.20.0"
        KIND_URL="https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${OS}-${ARCH}"

        echo -e "${CYAN}📥 Downloading kind from: ${KIND_URL}${NC}"

        # Create temp directory for download
        TEMP_DIR=$(mktemp -d)
        cd "$TEMP_DIR"

        # Download kind
        if curl -Lo ./kind "$KIND_URL"; then
            chmod +x ./kind

            # Try to install to /usr/local/bin (requires sudo)
            if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
                echo -e "${CYAN}📦 Installing kind to /usr/local/bin...${NC}"
                sudo mv ./kind /usr/local/bin/kind
            else
                # Fallback: install to ~/.local/bin
                echo -e "${CYAN}📦 Installing kind to ~/.local/bin...${NC}"
                mkdir -p ~/.local/bin
                mv ./kind ~/.local/bin/kind

                # Add ~/.local/bin to PATH if not already there
                if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
                    export PATH="$HOME/.local/bin:$PATH"
                    echo -e "${YELLOW}ℹ️  Added ~/.local/bin to PATH. You may need to restart your shell.${NC}"
                fi
            fi

            echo -e "${GREEN}✅ kind installed successfully${NC}"
        else
            echo -e "${RED}❌ Failed to download kind${NC}"
            cd "$PROJECT_DIR"
            rm -rf "$TEMP_DIR"
            return 1
        fi

        # Cleanup
        cd "$PROJECT_DIR"
        rm -rf "$TEMP_DIR"
    else
        echo -e "${GREEN}✅ kind CLI already installed${NC}"
    fi

    # Step 2: Setup Kind cluster
    echo -e "${CYAN}🏗️  Setting up Kind cluster...${NC}"

    # Create Kind cluster if it doesn't exist
    if ! kind get clusters | grep -q "ai-platform-demo"; then
        echo -e "${YELLOW}📦 Creating Kind cluster 'ai-platform-demo'...${NC}"
        kind create cluster --name ai-platform-demo --wait 30s
    else
        echo -e "${GREEN}✅ Kind cluster 'ai-platform-demo' already exists${NC}"
    fi

    # Verify cluster is ready
    echo -e "${CYAN}🔍 Verifying cluster status...${NC}"
    kubectl cluster-info --context kind-ai-platform-demo
    kubectl get nodes

    # Step 2: Run AI demo to generate specs
    echo -e "${CYAN}🤖 Running AI demo to generate Kubernetes APIs...${NC}"
    python3 examples/ai_demo.py

    # Step 3: Deploy generated Kubernetes resources
    echo -e "${CYAN}🚀 Deploying generated Kubernetes resources...${NC}"

    # Deploy generated CRDs if they exist
    for crd_file in generated_specs/kubernetes/*-crd.yaml; do
        if [[ -f "$crd_file" ]]; then
            echo -e "${YELLOW}📋 Deploying CRD: $(basename "$crd_file")${NC}"
            kubectl apply -f "$crd_file"
        fi
    done

    # Wait for CRDs to be established
    echo -e "${CYAN}⏳ Waiting for CRDs to be established...${NC}"
    sleep 10

    # Deploy sample instances if they exist
    for instance_file in generated_specs/kubernetes/*-instance.yaml; do
        if [[ -f "$instance_file" ]]; then
            echo -e "${YELLOW}📦 Deploying instance: $(basename "$instance_file")${NC}"
            kubectl apply -f "$instance_file"
        fi
    done

    # Step 4: Show deployed resources
    echo -e "${CYAN}📊 Showing deployed Kubernetes resources...${NC}"
    echo -e "${GREEN}=== Deployed Custom Resources ===${NC}"

    # Get all custom resources we created
    if kubectl get crds | grep -q "cnoe.io"; then
        kubectl get crds | grep "cnoe.io"

        echo -e "${GREEN}=== Resource Instances ===${NC}"
        # Show instances of our custom resources
        for crd in $(kubectl get crds -o name | grep "cnoe.io"); do
            resource_type=$(echo "$crd" | sed 's/customresourcedefinition.apiextensions.k8s.io\///' | sed 's/\..*//')
            if kubectl get "$resource_type" &>/dev/null; then
                echo -e "${YELLOW}$resource_type:${NC}"
                kubectl get "$resource_type" -o wide || echo "  No instances found"
                echo
            fi
        done
    else
        echo -e "${YELLOW}No custom resources deployed yet${NC}"
    fi

    # Show cluster info
    echo -e "${GREEN}=== Cluster Information ===${NC}"
    echo "Cluster: ai-platform-demo"
    echo "Context: kind-ai-platform-demo"
    echo "Use 'kubectl get <resource-type>' to explore your new APIs"

    echo -e "${GREEN}✅ Complete demo finished successfully!${NC}"
    echo -e "${CYAN}💡 Your Kubernetes APIs are now running in the Kind cluster${NC}"
    echo -e "${CYAN}💡 Try: kubectl describe databaseservice my-databaseservice-instance${NC}"
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
${CYAN}AI Kubernetes API Generator - Complete Demo Setup${NC}

${YELLOW}Usage:${NC}
    $0 [COMMAND] [OPTIONS]

${YELLOW}Commands:${NC}
    demo        Complete demo: Sets up Kind cluster, generates APIs, deploys to K8s
    interactive Start interactive mode for custom API generation
    test        Run the test suite
    setup       Set up the environment only (don't run anything)
    help        Show this help message

${YELLOW}Demo Command:${NC}
    $0 demo    # ONE COMMAND that does everything:
              # 1. Installs kubectl and kind automatically
              # 2. Creates Kind cluster automatically
              # 3. Runs AI to generate Kubernetes APIs
              # 4. Deploys CRDs and sample instances
              # 5. Shows running resources

${YELLOW}Environment Variables:${NC}
    OPENROUTER_API_KEY      Your OpenRouter API key (REQUIRED for AI)
    OPENROUTER_MODEL        OpenRouter model to use (default: deepseek/free)
    OPENAI_API_KEY          Alternative OpenAI API key
    AI_AGENT_DEBUG          Enable debug mode (default: false)

${YELLOW}Examples:${NC}
    # Set API key and run complete demo
    export OPENROUTER_API_KEY='sk-or-v1-your-key-here'
    $0 demo

    # Interactive mode
    $0 interactive

    # Run tests
    $0 test

    # Setup only
    $0 setup

${YELLOW}Prerequisites:${NC}
    - Docker (running)
    - curl (for downloading tools)
    - Everything else is installed automatically!

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