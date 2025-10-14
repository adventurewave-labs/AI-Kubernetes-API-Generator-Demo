# AI Kubernetes API Generator - Architecture Documentation

## System Overview

The AI Kubernetes API Generator is a Python-based tool that uses Large Language Models (LLMs) to transform natural language descriptions into Kubernetes Custom Resource Definitions (CRDs) and OpenAPI specifications.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   CLI Scripts   │  │   Rich Demo UI  │  │   REST API   │ │
│  │  (run.sh, demo) │  │ (impressive_    │  │  (optional)  │ │
│  │                 │  │   ai_demo.py)   │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Processing Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   AI Agent      │  │  Code Generator  │  │ Cluster Mgr │ │
│  │  (agent.py)     │  │  (codegen.py)    │  │ (cluster_   │ │
│  │                 │  │                 │  │  manager.py)│ │
│  │ • LLM Comm      │  │ • OpenAPI Spec   │  │ • Kind Setup │ │
│  │ • Request Parse │  │ • K8s Resources  │  │ • Deploy    │ │
│  │ • Validation    │  │ • File Output    │  │ • Health    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Data Models   │  │  File System    │  │ External    │ │
│  │ (CodegenRequest)│  │ (YAML/JSON)     │  │ Services    │ │
│  │                 │  │                 │  │ • OpenRouter│ │
│  │ • Pydantic      │  │ • Generated     │  │ • OpenAI    │ │
│  │ • Validation    │  │ • Config        │  │ • Kind      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. AI Agent (`src/ai_platform_generator/agent.py`)

**Purpose**: Handles communication with LLM providers and parses natural language input.

**Key Features**:
- **Multi-provider support**: Works with OpenRouter and OpenAI
- **Natural language parsing**: Converts user descriptions to structured requests
- **Error handling**: Graceful fallback to demo mode when API is unavailable
- **Request validation**: Ensures parsed requests meet minimum requirements

**Implementation**:
```python
class PlatformExtensionAgent:
    def __init__(self, api_key: str, model: str, verify_ssl: bool = True):
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
        self.system_prompt = self._build_system_prompt()

    def parse_request(self, user_input: str) -> CodegenRequest:
        # Process natural language with LLM
        # Return structured request object
```

**Data Flow**:
1. Receives natural language input
2. Sends to LLM with structured prompt
3. Parses JSON response
4. Validates and returns CodegenRequest object

### 2. Code Generator (`src/ai_platform_generator/codegen.py`)

**Purpose**: Generates OpenAPI specifications and Kubernetes YAML from structured requests.

**Key Features**:
- **OpenAPI 3.0 generation**: Creates standard API specifications
- **Kubernetes CRD generation**: Produces valid Custom Resource Definitions
- **Sample instance creation**: Generates example YAML files
- **Schema validation**: Ensures generated specs are valid

**Implementation**:
```python
class CodeGenerator:
    def generate_openapi_spec(self, request: CodegenRequest) -> Dict[str, Any]:
        # Build OpenAPI specification
        return {
            "openapi": "3.0.0",
            "info": {
                "title": f"{request.kind} API",
                "version": request.version,
                "description": request.description
            },
            "components": {"schemas": {request.kind: schema}}
        }

    def generate_kubernetes_resources(self, request: CodegenRequest) -> Dict[str, str]:
        # Generate CRD and instance YAML files
        pass
```

**Output Types**:
- OpenAPI JSON specifications
- Kubernetes CRD YAML files
- Sample instance YAML files
- Combined deployment manifests

### 3. Cluster Manager (`src/ai_platform_generator/cluster_manager.py`)

**Purpose**: Manages Kubernetes cluster operations for testing deployments.

**Key Features**:
- **Kind cluster management**: Creates and manages local clusters
- **Resource deployment**: Applies generated YAML to clusters
- **Health verification**: Checks deployment success
- **Prerequisites checking**: Validates required tools

**Implementation**:
```python
class KindClusterManager:
    def __init__(self, cluster_name: str = "ai-platform-demo"):
        self.cluster_name = cluster_name

    def ensure_cluster(self) -> bool:
        # Create cluster if it doesn't exist
        pass

    def deploy_resources(self, crd_path: str, instance_path: str) -> bool:
        # Apply CRD and instance to cluster
        pass
```

## Data Models

### CodegenRequest

```python
@dataclass
class CodegenRequest:
    group: str = "platform.cnoe.io"
    version: str = "v1alpha1"
    kind: str = ""
    spec_properties: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    output_dir: str = "/tmp/generated"
    description: str = ""

    def __post_init__(self):
        if not self.kind:
            raise ValueError("Kind is required")
        if not re.match(r'^[A-Z][a-zA-Z0-9]*$', self.kind):
            raise ValueError("Kind must be CamelCase")
```

## Processing Pipeline

### 1. Input Processing
```
Natural Language → LLM Provider → Structured Request → Validation
```

### 2. Code Generation
```
Structured Request → OpenAPI Spec → Kubernetes Resources → File Output
```

### 3. Deployment (Optional)
```
Generated Files → Kind Cluster → Resource Application → Health Check
```

## Error Handling Strategy

### Graceful Degradation

1. **AI Service Unavailable**: Falls back to demo mode with sample data
2. **Cluster Issues**: Generates files for manual deployment
3. **Validation Errors**: Provides helpful error messages
4. **Network Problems**: Retries with exponential backoff

### Error Recovery

```python
try:
    parsed_request = agent.parse_request(user_input)
except APIError:
    # Fall back to demo mode
    parsed_request = get_demo_request()
    print("Using demo mode due to API unavailability")
```

## Configuration

### Environment Variables

```bash
# Required for AI functionality
OPENROUTER_API_KEY="your-api-key"
OPENROUTER_MODEL="meta-llama/llama-3.2-3b-instruct:free"

# Optional
OPENAI_API_KEY="your-openai-key"
AI_AGENT_DEBUG="false"
AI_AGENT_OUTPUT_DIR="./generated"
```

### Configuration Files

```yaml
# config/agent_config.yaml
agent:
  name: "AI Scaffolding Agent"
  version: "1.0.0"

openai:
  model: "gpt-4"
  max_tokens: 4000
  temperature: 0.1

output:
  format: "yaml"
  validate_schemas: true
```

## Integration Points

### 1. LLM Providers
- **OpenRouter**: Primary provider with free models
- **OpenAI**: Alternative provider
- **Extensible**: Easy to add new providers

### 2. Kubernetes Ecosystem
- **Kind**: Local development clusters
- **kubectl**: Standard Kubernetes CLI
- **CRD Standards**: Follows Kubernetes conventions

### 3. File System
- **Generated Specs**: Output directory for generated files
- **Configuration**: YAML configuration files
- **Logging**: Structured logging output

## Security Considerations

### 1. API Key Management
- Environment variable storage
- No logging of sensitive data
- Secure transmission to providers

### 2. Input Validation
- Basic sanitization of user input
- Length limits to prevent abuse
- Content filtering where appropriate

### 3. Generated Resources
- Follows Kubernetes security best practices
- No privileged operations by default
- Proper RBAC considerations

## Performance Characteristics

### Typical Processing Times

| Operation | Typical Time | Dependencies |
|-----------|--------------|---------------|
| LLM Processing | 10-30 seconds | Network, API provider |
| OpenAPI Generation | < 5 seconds | Local processing |
| Kubernetes Generation | < 5 seconds | Local processing |
| Cluster Deployment | 60-180 seconds | Docker, Kind setup |

### Resource Usage

- **Memory**: < 200MB during normal operation
- **CPU**: Minimal during processing
- **Network**: API calls to LLM providers only
- **Storage**: < 10MB for generated files

## Testing Strategy

### 1. Unit Tests
- Individual component testing
- Mock external dependencies
- Validation logic testing

### 2. Integration Tests
- End-to-end workflow testing
- Real API integration (with test keys)
- Cluster deployment testing

### 3. Demo Tests
- Complete demo execution
- Generated file validation
- Cluster resource verification

## Future Enhancements

### Potential Improvements

1. **Advanced Schema Support**: Complex types, validation rules
2. **Controller Generation**: Go code for custom controllers
3. **Multi-Cluster Support**: Deploy across multiple clusters
4. **CI/CD Integration**: GitHub Actions, GitLab CI
5. **Template Library**: Pre-built patterns and templates
6. **Web Interface**: Browser-based tool for easier use

### Architecture Evolution

The current architecture is designed to be modular and extensible, allowing for easy addition of new features without major refactoring. The separation between AI processing, code generation, and deployment enables independent development of each component.
