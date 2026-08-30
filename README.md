# AI Kubernetes API Generator

Transform natural language descriptions into Kubernetes Custom Resource Definitions (CRDs) and OpenAPI specifications.

## Overview

Generate Kubernetes APIs from plain English descriptions. This tool helps developers create Kubernetes Custom Resources by using AI to parse natural language requests and generate OpenAPI specs and CRD YAML files.

## Features

- Generate OpenAPI 3.0 specifications from natural language descriptions
- Create Kubernetes Custom Resource Definitions (CRDs)
- Produce sample Kubernetes YAML files for testing
- Command-line interface with demo examples
- Kind cluster integration for testing deployments

## Quick Start

### Prerequisites

- Python 3.8+
- Docker (running)
- curl (usually pre-installed)
- OpenRouter API key (free tier available)

**Note**: kubectl and kind are installed automatically by the demo script.

### One-Command Demo Setup

```bash
# Clone the repository
git clone https://github.com/adventurewave-labs/AI-Kubernetes-API-Generator-Demo.git
cd AI-Kubernetes-API-Generator-Demo

# Get your free OpenRouter API key from https://openrouter.ai
export OPENROUTER_API_KEY="your-openrouter-api-key-here"

# Run the complete demo
./run.sh demo
```

**The demo command automatically:**
1. Installs kubectl and kind CLI tools
2. Creates Kind cluster if needed
3. Generates Kubernetes APIs from natural language
4. Deploys CRDs and sample instances to the cluster
5. Shows running resources

### Manual Setup

If you prefer to install tools manually:

```bash
# Install kubectl and kind manually, then:
kind create cluster --name ai-platform-demo

# Run just the AI demo (no automatic setup)
python examples/ai_demo.py

# Deploy generated resources manually
kubectl apply -f generated_specs/kubernetes/databaseservice-crd.yaml
kubectl apply -f generated_specs/kubernetes/databaseservice-instance.yaml
```

### Verify Demo Results

After the demo completes, explore your new Kubernetes APIs:

```bash
# Check deployed custom resources
kubectl get crds | grep cnoe.io

# View your new API instances
kubectl get databaseservices.database.cnoe.io
kubectl describe databaseservice my-databaseservice-instance

# Explore the cluster
kubectl get all -A
```

## Usage Examples

Describe what you want to create in plain English:

- "PostgreSQL database clusters with replication and backup scheduling"
- "Redis cluster management with memory and CPU configuration"
- "Monitoring service API with configurable intervals and alerts"

### Generated Output

The AI generates these files:

- `generated_specs/database_demo.json` - OpenAPI 3.0 specification
- `generated_specs/kubernetes/databaseservice-crd.yaml` - Kubernetes CRD
- `generated_specs/kubernetes/databaseservice-instance.yaml` - Sample instance

### Example Generated CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databaseservices.database.cnoe.io
spec:
  group: database.cnoe.io
  versions:
  - name: v1alpha1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              connectionString:
                type: string
                description: Database connection string
              backupSchedule:
                type: string
                description: Cron schedule for backups
              autoScaling:
                type: boolean
                description: Enable auto-scaling
```

## Testing

```bash
# Run tests
python3 -m pytest tests/ -v
```

## Configuration

Required environment variables:

```bash
export OPENROUTER_API_KEY="your-openrouter-api-key"
export OPENROUTER_MODEL="meta-llama/llama-3.2-3b-instruct:free"
```

Get your free API key from [OpenRouter.ai](https://openrouter.ai)

## How It Works

1. **Describe API**: Explain what you want in natural language
2. **AI Processing**: The AI parses your description into a structured request
3. **Generate Spec**: Creates OpenAPI 3.0 specification from the parsed request
4. **Deploy CRD**: Apply generated Kubernetes YAML to your cluster
5. **Use Resource**: Interact with your new custom resource

Example deployment:
```bash
kubectl apply -f generated_specs/kubernetes/databaseservice-crd.yaml
kubectl get databaseservices.database.cnoe.io
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

Built with [Pydantic](https://docs.pydantic.dev/) and follows [OpenAPI 3.0](https://swagger.io/specification/) standards.
