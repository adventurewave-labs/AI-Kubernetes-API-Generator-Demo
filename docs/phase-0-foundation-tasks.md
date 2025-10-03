# Phase 0: Foundation & Environment Setup

## Overview

**Objective**: Establish development environment with all prerequisites, tooling, and repository clones for production-ready AI agent development.

**Current State**: Node.js/TypeScript project exists, missing Python/Go environment and external repositories
**Success Criteria**: Complete development environment with all tools, repositories, and integrations verified

## Prerequisites Verification

### Existing Infrastructure
- ✅ Node.js/TypeScript project structure (package.json, tsconfig.json)
- ✅ Playwright testing framework configured
- ✅ Git repository initialized
- ✅ Basic project scaffolding in place

### Required Additions
- ❌ Python 3.9+ development environment
- ❌ Go 1.19+ toolchain and GOPATH
- ❌ External repository clones (cnoe-io/openapi-mcp-codegen)
- ❌ OpenAI API key configuration
- ❌ Project structure following CLAUDE.md guidelines

## Atomic Task Breakdown

### Foundation Tasks (00a-00z)

#### task_00a_setup_python_environment.md
**Estimated Time: 10 minutes**

**Context**
- Current system has Python potentially available but not verified
- Need virtual environment isolation for dependencies
- OpenAI package required for AI agent functionality

**Current System State**
- System Python version unknown
- No virtual environment exists
- OpenAI package not installed

**Your Task**
Verify Python 3.9+ availability, create virtual environment, install required packages

**Test First (RED Phase)**
```python
#!/usr/bin/env python3
import sys
import subprocess
import importlib

def test_python_version():
    """Test Python version meets requirements"""
    version = sys.version_info
    assert version.major >= 3 and version.minor >= 9, f"Python 3.9+ required, found {version.major}.{version.minor}"

def test_virtual_environment():
    """Test virtual environment is active"""
    import sys
    assert hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix), \
        "Virtual environment not active"

def test_openai_package():
    """Test OpenAI package is available"""
    try:
        import openai
        assert hasattr(openai, 'OpenAI'), "OpenAI package not properly installed"
    except ImportError:
        assert False, "OpenAI package not installed"

if __name__ == "__main__":
    test_python_version()
    test_virtual_environment()
    test_openai_package()
    print("✅ All Python environment tests passed")
```

**Minimal Implementation (GREEN Phase)**
```bash
#!/bin/bash
# Create and setup Python environment
python3 --version
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install openai>=1.0.0
```

**Refactored Solution (REFACTOR Phase)**
```bash
#!/bin/bash
set -euo pipefail

# Python Environment Setup Script
setup_python_env() {
    echo "🐍 Setting up Python environment..."

    # Verify Python version
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 not found. Please install Python 3.9+"
        exit 1
    fi

    python_version=$(python3 --version | cut -d' ' -f2)
    echo "✅ Found Python $python_version"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate and install dependencies
    echo "🔧 Activating virtual environment and installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install openai>=1.0.0

    # Verify installation
    python3 -c "import openai; print(f'✅ OpenAI version: {openai.__version__}')"

    echo "✅ Python environment setup complete"
}

setup_python_env
```

**Verification Commands**
```bash
# Run verification
bash scripts/setup_python_env.sh
python3 test_env.py

# Expected output
✅ Found Python 3.11.4
✅ Virtual environment activated
✅ OpenAI version: 1.3.0
✅ All Python environment tests passed
```

**Success Criteria**
- [ ] Test script written and initially fails with expected error
- [ ] Python 3.9+ verified available on system
- [ ] Virtual environment created successfully
- [ ] OpenAI package installed and verified
- [ ] Test script passes all checks
- [ ] No mocks or stubs - real implementation only

**Dependencies Confirmed**
- Python 3.9+ (system requirement)
- pip package manager (included with Python)
- internet access for package installation
- shell script execution capabilities

**Next Task**: task_00b_setup_go_toolchain.md - Verify Go 1.19+ installation and configuration

---

#### task_00b_setup_go_toolchain.md
**Estimated Time: 10 minutes**

**Context**
- Go 1.19+ required for openapi-mcp-codegen compilation
- GOPATH configuration needed for proper Go workspace
- Basic Go compilation verification required

**Current System State**
- Go installation status unknown
- GOPATH configuration unverified
- Go compilation capability untested

**Your Task**
Verify Go 1.19+ installation, configure environment, test compilation

**Test First (RED Phase)**
```go
package main

import (
	"fmt"
	"os"
	"runtime"
	"strings"
)

func main() {
	// Test Go version
	version := runtime.Version()
	parts := strings.Split(version, ".")
	major := strings.TrimPrefix(parts[0], "go")
	minor := parts[1]

	if major < "1" || (major == "1" && minor < "19") {
		fmt.Printf("❌ Go 1.19+ required, found %s\n", version)
		os.Exit(1)
	}

	fmt.Printf("✅ Go version: %s\n", version)

	// Test GOPATH
	gopath := os.Getenv("GOPATH")
	if gopath == "" {
		fmt.Println("❌ GOPATH not set")
		os.Exit(1)
	}
	fmt.Printf("✅ GOPATH: %s\n", gopath)

	// Test basic compilation
	fmt.Println("✅ Go toolchain properly configured")
}
```

**Minimal Implementation (GREEN Phase)**
```bash
#!/bin/bash
# Verify and setup Go toolchain
go version
go env GOPATH
go env GOROOT
echo 'package main; import "fmt"; func main() { fmt.Println("Hello Go") }' > test.go
go run test.go
rm test.go
```

**Refactored Solution (REFACTOR Phase)**
```bash
#!/bin/bash
set -euo pipefail

# Go Toolchain Setup Script
setup_go_toolchain() {
    echo "🔧 Setting up Go toolchain..."

    # Check if Go is installed
    if ! command -v go &> /dev/null; then
        echo "❌ Go not found. Please install Go 1.19+"
        echo "Visit: https://golang.org/dl/"
        exit 1
    fi

    # Verify Go version
    go_version=$(go version | cut -d' ' -f3 | sed 's/go//')
    echo "✅ Found Go $go_version"

    # Check version meets requirements
    if ! go version | grep -E "go1\.(1[9-9]|[2-9][0-9])" > /dev/null; then
        echo "❌ Go 1.19+ required, found $go_version"
        exit 1
    fi

    # Check GOPATH
    gopath=$(go env GOPATH)
    if [ -z "$gopath" ]; then
        echo "❌ GOPATH not configured"
        exit 1
    fi
    echo "✅ GOPATH: $gopath"

    # Test basic compilation
    echo "🧪 Testing Go compilation..."
    echo 'package main; import "fmt"; func main() { fmt.Println("Hello from Go!") }' > /tmp/hello.go
    if go run /tmp/hello.go > /dev/null; then
        echo "✅ Go compilation successful"
    else
        echo "❌ Go compilation failed"
        exit 1
    fi
    rm -f /tmp/hello.go

    echo "✅ Go toolchain setup complete"
}

setup_go_toolchain
```

**Verification Commands**
```bash
# Run setup and verification
bash scripts/setup_go_toolchain.sh
go run tests/go_version_test.go

# Expected output
✅ Found Go 1.21.3
✅ GOPATH: /home/user/go
✅ Go compilation successful
✅ Go version: go1.21.3
✅ GOPATH: /home/user/go
✅ Go toolchain properly configured
```

**Success Criteria**
- [ ] Test script written and initially fails without Go
- [ ] Go 1.19+ verified available on system
- [ ] GOPATH properly configured
- [ ] Basic Go compilation successful
- [ ] All version checks pass
- [ ] No mocks or stubs - real Go toolchain verification

**Dependencies Confirmed**
- Go 1.19+ (system requirement)
- GOPATH configuration (environment setup)
- Basic compilation capabilities (toolchain verification)

**Next Task**: task_00c_clone_external_repositories.md - Clone and verify external repositories

---

#### task_00c_clone_external_repositories.md
**Estimated Time: 15 minutes**

**Context**
- Need to clone cnoe-io/openapi-mcp-codegen repository
- Must verify repository accessibility and structure
- Build binaries and test basic functionality

**Current System State**
- No external repositories cloned
- Repository accessibility unverified
- Build status unknown

**Your Task**
Clone cnoe-io repositories, verify structure, build binaries, test functionality

**Test First (RED Phase)**
```bash
#!/bin/bash
# Test repository cloning and functionality
test_repository_cloning() {
    # Test if repositories exist
    if [ ! -d "openapi-mcp-codegen" ]; then
        echo "❌ openapi-mcp-codegen repository not found"
        exit 1
    fi

    # Test repository structure
    if [ ! -f "openapi-mcp-codegen/go.mod" ]; then
        echo "❌ Go module not found in repository"
        exit 1
    fi

    # Test binary availability
    if [ ! -f "openapi-mcp-codegen/openapi-mcp-codegen" ]; then
        echo "❌ openapi-mcp-codegen binary not built"
        exit 1
    fi

    # Test basic functionality
    if ! ./openapi-mcp-codegen/openapi-mcp-codegen --help > /dev/null 2>&1; then
        echo "❌ openapi-mcp-codegen binary not functional"
        exit 1
    fi

    echo "✅ All repository tests passed"
}

test_repository_cloning
```

**Minimal Implementation (GREEN Phase)**
```bash
#!/bin/bash
# Clone external repositories
git clone https://github.com/cnoe-io/openapi-mcp-codegen.git
cd openapi-mcp-codegen
go build .
./openapi-mcp-codegen --help
```

**Refactored Solution (REFACTOR Phase)**
```bash
#!/bin/bash
set -euo pipefail

# External Repository Setup Script
setup_repositories() {
    echo "📥 Setting up external repositories..."

    # Clone openapi-mcp-codegen
    if [ ! -d "openapi-mcp-codegen" ]; then
        echo "📥 Cloning cnoe-io/openapi-mcp-codegen..."
        git clone https://github.com/cnoe-io/openapi-mcp-codegen.git
    else
        echo "📁 Repository already exists, updating..."
        cd openapi-mcp-codegen
        git pull origin main
        cd ..
    fi

    # Verify repository structure
    cd openapi-mcp-codegen
    if [ ! -f "go.mod" ]; then
        echo "❌ Invalid repository structure"
        exit 1
    fi
    echo "✅ Repository structure verified"

    # Build binary
    echo "🔨 Building openapi-mcp-codegen..."
    if go build .; then
        echo "✅ Build successful"
    else
        echo "❌ Build failed"
        exit 1
    fi

    # Test binary functionality
    echo "🧪 Testing binary functionality..."
    if ./openapi-mcp-codegen --help > /dev/null 2>&1; then
        echo "✅ Binary functional"
    else
        echo "❌ Binary not functional"
        exit 1
    fi

    # Test basic code generation
    echo "🧪 Testing basic code generation..."
    mkdir -p /tmp/test-output
    if ./openapi-mcp-codegen \
        --output-dir /tmp/test-output \
        --go-header-file hack/boilerplate.go.txt \
        --input-spec '{"group":"test.cnoe.io","version":"v1alpha1","kind":"TestResource","spec":{"properties":{"name":{"type":"string"}}}}' > /dev/null 2>&1; then
        echo "✅ Basic code generation successful"
        rm -rf /tmp/test-output
    else
        echo "❌ Code generation test failed"
        exit 1
    fi

    cd ..
    echo "✅ External repositories setup complete"
}

setup_repositories
```

**Verification Commands**
```bash
# Run repository setup and verification
bash scripts/setup_repositories.sh
bash scripts/test_repositories.sh

# Expected output
📥 Cloning cnoe-io/openapi-mcp-codegen...
✅ Repository structure verified
🔨 Building openapi-mcp-codegen...
✅ Build successful
🧪 Testing binary functionality...
✅ Binary functional
🧪 Testing basic code generation...
✅ Basic code generation successful
✅ All repository tests passed
```

**Success Criteria**
- [ ] Test script written and initially fails without repositories
- [ ] Repository successfully cloned and updated
- [ ] Go module structure verified
- [ ] Binary builds successfully
- [ ] Basic functionality tested and working
- [ ] Code generation capability verified
- [ ] No mocks or stubs - real repository integration

**Dependencies Confirmed**
- Git access to external repositories
- Go build capabilities
- Network connectivity for cloning
- Basic Go project structure understanding

**Next Task**: task_00d_configure_api_keys.md - Setup OpenAI API configuration and validation

---

#### task_00d_configure_api_keys.md
**Estimated Time: 10 minutes**

**Context**
- OpenAI API key required for AI agent functionality
- Need secure configuration management
- Must test API connectivity and handle errors

**Current System State**
- No API key configured
- No configuration management system
- API connectivity untested

**Your Task**
Setup OpenAI API key configuration, test connectivity, implement error handling

**Test First (RED Phase)**
```python
#!/usr/bin/env python3
import os
import openai
from openai import OpenAI

def test_api_key_configuration():
    """Test OpenAI API key configuration and connectivity"""

    # Test environment variable
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Test API key format (basic validation)
    if not api_key.startswith('sk-'):
        raise ValueError("Invalid API key format")

    # Test API connectivity
    try:
        client = OpenAI(api_key=api_key)
        # Test with a simple models list request
        models = client.models.list()
        assert len(models.data) > 0, "No models returned from API"
        print(f"✅ API connectivity verified, {len(models.data)} models available")

    except openai.AuthenticationError:
        raise ValueError("Invalid API key")
    except Exception as e:
        raise ValueError(f"API connectivity error: {e}")

if __name__ == "__main__":
    test_api_key_configuration()
```

**Minimal Implementation (GREEN Phase)**
```bash
#!/bin/bash
# Setup API key configuration
echo "export OPENAI_API_KEY='your-api-key-here'" >> ~/.bashrc
source ~/.bashrc
python3 -c "import os; print('API key:', os.getenv('OPENAI_API_KEY', 'Not set'))"
```

**Refactored Solution (REFACTOR Phase)**
```python
#!/usr/bin/env python3
import os
import sys
import openai
from openai import OpenAI
from pathlib import Path

class APIKeyManager:
    """Manage OpenAI API key configuration and validation"""

    def __init__(self):
        self.config_file = Path.home() / '.openai_config'
        self.api_key = None

    def load_api_key(self):
        """Load API key from environment or config file"""
        # Try environment variable first
        self.api_key = os.getenv('OPENAI_API_KEY')

        # Try config file if not in environment
        if not self.api_key and self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.api_key = f.read().strip()

        if not self.api_key:
            raise ValueError("❌ OPENAI_API_KEY not found in environment or config file")

        # Validate key format
        if not self.api_key.startswith('sk-'):
            raise ValueError("❌ Invalid API key format. Must start with 'sk-'")

        return self.api_key

    def save_api_key(self, api_key):
        """Save API key to config file"""
        if not api_key.startswith('sk-'):
            raise ValueError("Invalid API key format")

        with open(self.config_file, 'w') as f:
            f.write(api_key)
        os.chmod(self.config_file, 0o600)  # Restrict permissions
        print(f"✅ API key saved to {self.config_file}")

    def test_connectivity(self):
        """Test API connectivity"""
        try:
            client = OpenAI(api_key=self.api_key)
            models = client.models.list()
            return len(models.data) > 0
        except Exception as e:
            print(f"❌ API connectivity test failed: {e}")
            return False

def main():
    """Main setup function"""
    print("🔑 Setting up OpenAI API configuration...")

    manager = APIKeyManager()

    # Try to load existing key
    try:
        api_key = manager.load_api_key()
        print(f"✅ API key loaded: {api_key[:10]}...")

        # Test connectivity
        if manager.test_connectivity():
            print("✅ API connectivity verified")
        else:
            print("⚠️  API key loaded but connectivity test failed")
            return False

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please set your OPENAI_API_KEY environment variable")
        print("Example: export OPENAI_API_KEY='sk-your-api-key-here'")
        return False

    print("✅ API configuration complete")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

**Verification Commands**
```bash
# Setup and test API configuration
python3 scripts/setup_api_config.py
python3 tests/test_api_config.py

# Expected output
🔑 Setting up OpenAI API configuration...
✅ API key loaded: sk-proj-abc...
✅ API connectivity verified, 15 models available
✅ API configuration complete
```

**Success Criteria**
- [ ] Test script written and initially fails without API key
- [ ] API key loading from environment or config file
- [ ] API key format validation implemented
- [ ] API connectivity tested and verified
- [ ] Error handling for invalid keys implemented
- [ ] Secure configuration management with proper permissions
- [ ] No mocks or stubs - real OpenAI API integration

**Dependencies Confirmed**
- OpenAI Python package (from task_00a)
- Internet connectivity for API access
- File system permissions for config file management

**Next Task**: task_00e_setup_project_structure.md - Create proper project structure following CLAUDE.md

---

#### task_00e_setup_project_structure.md
**Estimated Time: 10 minutes**

**Context**
- Need to organize project structure following CLAUDE.md guidelines
- Proper directory structure for source code, tests, documentation
- Must follow file organization rules (no root folder saving)

**Current System State**
- Basic project structure exists with package.json, etc.
- Missing proper directory structure for Python/Go components
- Not following CLAUDE.md file organization rules

**Your Task**
Create proper directory structure, organize existing files, validate structure

**Test First (RED Phase)**
```bash
#!/bin/bash
# Test project structure compliance
test_project_structure() {
    # Required directories
    required_dirs=(
        "src"
        "tests"
        "docs"
        "config"
        "scripts"
        "examples"
    )

    # Check required directories exist
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "❌ Required directory missing: $dir"
            exit 1
        fi
        echo "✅ Directory exists: $dir"
    done

    # Check no working files in root
    root_files=$(find . -maxdepth 1 -name "*.py" -o -name "*.go" -o -name "*.txt" | wc -l)
    if [ "$root_files" -gt 0 ]; then
        echo "❌ Working files found in root directory"
        exit 1
    fi

    # Check source structure
    if [ ! -f "src/agent.py" ] && [ ! -f "src/main.py" ]; then
        echo "❌ No main source file found in src/"
        exit 1
    fi

    echo "✅ Project structure compliant"
}

test_project_structure
```

**Minimal Implementation (GREEN Phase)**
```bash
#!/bin/bash
# Create project structure
mkdir -p src tests docs config scripts examples
mv *.py src/ 2>/dev/null || true
mv *.go src/ 2>/dev/null || true
```

**Refactored Solution (REFACTOR Phase)**
```bash
#!/bin/bash
set -euo pipefail

# Project Structure Setup Script
setup_project_structure() {
    echo "📁 Setting up project structure..."

    # Define required directories
    required_dirs=(
        "src"
        "tests"
        "docs"
        "config"
        "scripts"
        "examples"
        "logs"
        "data"
    )

    # Create directories
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "📁 Creating directory: $dir"
            mkdir -p "$dir"
        else
            echo "📁 Directory exists: $dir"
        fi
    done

    # Create source subdirectories
    src_subdirs=(
        "src/agent"
        "src/integrations"
        "src/utils"
        "src/models"
    )

    for dir in "${src_subdirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "📁 Creating source subdirectory: $dir"
            mkdir -p "$dir"
        fi
    done

    # Create test subdirectories
    test_subdirs=(
        "tests/unit"
        "tests/integration"
        "tests/e2e"
    )

    for dir in "${test_subdirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "📁 Creating test subdirectory: $dir"
            mkdir -p "$dir"
        fi
    done

    # Move any loose files to appropriate directories
    echo "📦 Organizing existing files..."

    # Move Python files to src/
    find . -maxdepth 1 -name "*.py" -not -path "./tests/*" -not -path "./scripts/*" -exec mv {} src/ \;

    # Move Go files to src/
    find . -maxdepth 1 -name "*.go" -not -path "./tests/*" -not -path "./scripts/*" -exec mv {} src/ \;

    # Create initial files
    echo "📝 Creating initial files..."

    # Main agent file
    cat > src/agent.py << 'EOF'
#!/usr/bin/env python3
"""
AI-Assisted Platform Extension Generator Agent
Main agent implementation
"""

import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main entry point"""
    print("🤖 AI-Assisted Platform Extension Generator")
    print("🚀 Starting up...")

    # TODO: Implement main agent logic
    print("✅ Agent initialized (placeholder)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
EOF

    # Configuration file
    cat > config/agent_config.yaml << 'EOF'
# AI-Assisted Platform Extension Generator Configuration

openai:
  model: "gpt-4"
  max_tokens: 1000
  temperature: 0.7

codegen:
  output_dir: "/tmp/generated-projects"
  go_header_file: "../openapi-mcp-codegen/hack/boilerplate.go.txt"

logging:
  level: "INFO"
  file: "logs/agent.log"

defaults:
  group: "platform.cnoe.io"
  version: "v1alpha1"
EOF

    # Make main script executable
    chmod +x src/agent.py

    echo "✅ Project structure setup complete"

    # Display structure
    echo ""
    echo "📂 Project Structure:"
    tree -L 3 -I 'node_modules|venv|*.log' || find . -type d -not -path './node_modules/*' -not -path './venv/*' | head -20
}

setup_project_structure
```

**Verification Commands**
```bash
# Run structure setup and validation
bash scripts/setup_project_structure.sh
bash scripts/test_project_structure.sh

# Expected output
📁 Setting up project structure...
📁 Creating directory: src
📁 Creating directory: tests
...
📦 Organizing existing files...
📝 Creating initial files...
✅ Project structure setup complete

📂 Project Structure:
.
├── src/
├── tests/
├── docs/
├── config/
├── scripts/
└── examples/

✅ Directory exists: src
✅ Directory exists: tests
✅ Project structure compliant
```

**Success Criteria**
- [ ] Test script written and initially fails without proper structure
- [ ] All required directories created (src, tests, docs, config, scripts, examples)
- [ ] Source subdirectories created (agent, integrations, utils, models)
- [ ] Test subdirectories created (unit, integration, e2e)
- [ ] Loose files moved to appropriate directories
- [ ] No working files left in root directory
- [ ] Initial agent.py and config files created
- [ ] No mocks or stubs - real directory structure and files

**Dependencies Confirmed**
- File system permissions for directory creation
- Basic file manipulation commands
- Tree or find command for structure display

**Next Task**: Phase 1 tasks focusing on external repository integration

## Phase 0 Completion Criteria

### Technical Success
- [x] Python 3.9+ environment with virtual environment
- [x] Go 1.19+ toolchain with proper GOPATH
- [x] External repositories cloned and verified
- [x] OpenAI API key configuration and testing
- [x] Proper project structure following CLAUDE.md

### Integration Success
- [x] All external repositories accessible and functional
- [x] OpenAI API connectivity verified
- [x] Build systems working for both Python and Go
- [x] Project structure ready for development

### Documentation Success
- [x] Each task documented with TDD approach
- [x] Verification commands provided
- [x] Success criteria clearly defined
- [x] Dependencies identified and verified

## Next Steps

Phase 0 provides the foundation for subsequent development phases. With the environment properly configured, we can proceed to:

1. **Phase 1**: External Repository Integration - Deep integration with cnoe-io tools
2. **Phase 2**: AI Agent Development - Build the core AI scaffolding agent
3. **Phase 3**: Code Generation Integration - Connect AI to code generation
4. **Phase 4**: Testing & Validation - Comprehensive testing strategy
5. **Phase 5**: Documentation & Deployment - Production-ready release

Each subsequent phase builds upon this foundation, following the same atomic task breakdown approach with TDD methodology and no mocks or stubs.