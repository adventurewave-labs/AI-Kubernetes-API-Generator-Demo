# AI-Assisted Platform Extension Generator - Usage Guide

## 🚀 Quick Start

This tool helps you generate Kubernetes platform extensions through natural language descriptions. Simply describe what you want to build, and the AI will generate a complete Kubernetes controller with CRDs.

### Prerequisites

1. **Python 3.12+** installed
2. **OpenRouter API key** - Get one at [openrouter.ai](https://openrouter.ai/)

### Setup

```bash
# Install dependencies
pip install openai click rich pydantic

# Set your OpenRouter API key
export OPENROUTER_API_KEY="your-api-key-here"
```

## 🎯 Usage Examples

### 1. Interactive Mode (Recommended for beginners)

```bash
python -m src.ai_platform_generator.cli interactive
```

You'll see a welcome screen with examples. Just type what you want to create:

```
Describe the Kubernetes API you want to create: Create a VectorDB API with engine_type and replicas fields
```

The AI will:
- Parse your request
- Show you the parsed structure
- Generate the complete controller code
- Display next steps for deployment

### 2. Direct Generation

```bash
# Generate a VectorDB controller
python -m src.ai_platform_generator.cli generate "Create a VectorDB API for AI workloads with engine_type (string) and replicas (integer) fields" --format json

# Output will show the parsed request:
{
  "kind": "VectorDB",
  "group": "platform.ai.cnoe.io",
  "version": "v1alpha1",
  "spec_properties": {
    "engine_type": {"type": "string"},
    "replicas": {"type": "integer"}
  },
  "output_dir": "/tmp/vectordb",
  "description": "Vector database API for AI workloads"
}
```

### 3. Build from Saved Request

```bash
# Save a request to file
python -m src.ai_platform_generator.cli generate "Create a CacheCluster with size and memory" --format json > cache-cluster.json

# Build the actual code
python -m src.ai_platform_generator.cli build cache-cluster.json --output-dir ./my-cache-cluster
```

## 📚 Example Requests

### Vector Database API
```bash
"Create a VectorDB API for AI workloads with engine_type (string), replicas (integer), and storage_size (string) fields"
```

### Cache Cluster
```bash
"Build a CacheCluster for microservices with size (string), memory (string), and port (integer) fields"
```

### Database Backup
```bash
"I need a DatabaseBackup resource with schedule (string), retention_days (integer), and enabled (boolean)"
```

### Configuration Template
```bash
"Make a ConfigTemplate with template_name (string), variables (object), and namespace (string)"
```

### Service Mesh Route
```bash
"Create a MeshRoute with service_name (string), target_service (string), weight (integer), and headers (object)"
```

## 🏗️ Generated Code Structure

When you run a build command, the generator creates a complete Kubernetes controller:

```
/tmp/vectordb/
├── main.go                    # Controller entry point
├── go.mod                     # Go module with dependencies
├── Dockerfile                 # Container build instructions
├── api/
│   └── v1alpha1/
│       └── vectordb_types.go  # CRD type definitions
└── internal/
    └── controller/
        └── vectordb_controller.go  # Controller reconciliation logic
```

### Key Generated Files

**main.go**: Entry point that sets up the controller manager
```go
func main() {
    mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
        Scheme:             scheme,
        MetricsBindAddress: metricsAddr,
        Port:               9443,
        HealthProbeBindAddress: probeAddr,
        LeaderElection:     enableLeaderElection,
    })
    // Controller setup here
}
```

**types.go**: Kubernetes API type definitions
```go
// VectorDBSpec defines the desired state of VectorDB
type VectorDBSpec struct {
    engine_type string `json:"engine_type"`
    replicas    int32  `json:"replicas"`
    storage_size string `json:"storage_size"`
}
```

**controller.go**: Reconciliation logic
```go
func (r *VectorDBReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Your reconciliation logic here
}
```

## 🎛️ Advanced Usage

### Custom AI Model

```bash
python -m src.ai_platform_generator.cli interactive --model "anthropic/claude-3-opus"
```

### Custom Output Directory

```bash
python -m src.ai_platform_generator.cli generate "Create a TestResource" --output-dir ./my-project
```

### YAML Output Format

```bash
python -m src.ai_platform_generator.cli generate "Create a TestResource" --format yaml
```

## 🚀 Deployment Steps

After generating your controller:

1. **Navigate to output directory**:
   ```bash
   cd /tmp/your-resource
   ```

2. **Initialize Go module**:
   ```bash
   go mod tidy
   ```

3. **Build Docker image**:
   ```bash
   docker build -t your-resource-controller .
   ```

4. **Deploy to Kubernetes**:
   ```bash
   kubectl apply -f config/crd/bases/
   kubectl apply -f config/manager/
   ```

5. **Test your resource**:
   ```bash
   kubectl apply -f - <<EOF
   apiVersion: platform.test.io/v1alpha1
   kind: VectorDB
   metadata:
     name: my-vectordb
   spec:
     engine_type: "pinecone"
     replicas: 3
     storage_size: "100Gi"
   EOF
   ```

## 🧪 Testing Your Generated Controller

```bash
# Run unit tests
cd /tmp/your-resource
go test ./...

# Run integration tests
make test-integration

# Run controller locally
make run
```

## 🔧 Configuration Options

### Environment Variables
- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `DEFAULT_MODEL`: AI model to use (default: `anthropic/claude-3.5-sonnet`)

### Supported Data Types
- `string`: Text values
- `integer`: Whole numbers
- `number`: Decimal numbers
- `boolean`: true/false values
- `array`: Lists of items
- `object`: Nested key-value pairs

## 🔍 Request Best Practices

### DO ✅
- Be specific: `"Create a VectorDB with engine_type (string) and replicas (integer)"`
- Provide context: `"for AI workloads"` or `"for microservices"`
- Use CamelCase for resource names: `"VectorDB"`, `"CacheCluster"`
- Specify field types in parentheses: `"port (integer)"`

### DON'T ❌
- Be vague: `"Make something for databases"`
- Use lowercase resource names: `"vectordb"` (use `"VectorDB"`)
- Forget field types: `"Create a VectorDB with engine_type"`
- Overcomplicate: Keep descriptions focused and clear

## 🆘 Troubleshooting

### Common Issues

**"API key not found"**
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

**"Invalid kind format"**
- Use CamelCase: `VectorDB` instead of `vectordb`

**"Validation errors"**
- Ensure at least one field is specified
- Check that field types are valid (string, integer, boolean, array, object)

**Code generation fails**
- Check that output directory is writable
- Ensure you have sufficient disk space
- Verify Go is installed for Kubernetes controller generation

### Debug Mode

```bash
# Enable verbose output
python -m src.ai_platform_generator.cli generate "your request" --debug
```

## 📖 Next Steps

1. **Try the examples command**:
   ```bash
   python -m src.ai_platform_generator.cli examples
   ```

2. **Generate your first controller**:
   ```bash
   python -m src.ai_platform_generator.cli interactive
   ```

3. **Deploy and test**:
   Follow the deployment steps above to run your controller in Kubernetes

4. **Customize the generated code**:
   Modify the controller logic to implement your specific business logic

Need help? Check the [main README](README.md) for detailed architecture and contributing guidelines.