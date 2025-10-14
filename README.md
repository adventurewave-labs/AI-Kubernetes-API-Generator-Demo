# AI Kubernetes API Generator v1.0.1

Transform natural language descriptions into Kubernetes Custom Resource Definitions (CRDs) and OpenAPI specifications.

## Overview

Generate production-ready Kubernetes APIs from plain English descriptions. Perfect for platform engineers, DevOps teams, and developers building Kubernetes operators and custom resources.

## Features

- Generate OpenAPI 3.0 specifications from natural language
- Create Kubernetes Custom Resource Definitions (CRDs)
- Produce sample Kubernetes YAML files
- Interactive demo with pre-built examples
- Simple command-line interface

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Docker (running)
- curl (usually pre-installed)
- OpenRouter API key (free tier available)

**Note**: kubectl and kind are installed automatically by the demo script!

### One-Command Demo Setup

```bash
# Clone the repository
git clone https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo.git
cd AI-Kubernetes-API-Generator-Demo

# Install dependencies
pip install -r requirements.txt

# Get your free OpenRouter API key from https://openrouter.ai
export OPENROUTER_API_KEY="your-openrouter-api-key-here"

# RUN THE COMPLETE DEMO - One command does everything!
./run.sh demo
```

**The demo command automatically:**
1. 🔧 Installs kubectl and kind CLI tools
2. ✅ Creates Kind cluster if needed
3. 🤖 Generates Kubernetes APIs from natural language
4. 🚀 Deploys CRDs and sample instances to the cluster
5. 📊 Shows running resources and usage instructions

### Manual Setup (Alternative)

If you prefer to install tools manually:

```bash
# Install kubectl and kind manually, then:
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# Create Kind cluster
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
kubectl get databaseservices.cnoe.io
kubectl describe databaseservice my-databaseservice-instance

# Explore the cluster
kubectl get all -A
```

## Usage Examples

Describe what you want to create in plain English:

- "PostgreSQL database clusters with replication and backup scheduling"
- "Redis cluster management with memory and CPU configuration"
- "Monitoring service API with configurable intervals and alerts"
- "Machine learning pipeline API with training parameters"

### Generated Output

The AI generates these files:

- `generated_specs/databaseservice_demo.json` - OpenAPI 3.0 specification
- `generated_specs/kubernetes/databaseservice-crd.yaml` - Kubernetes CRD
- `generated_specs/kubernetes/databaseservice-instance.yaml` - Sample instance

### Example Generated CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databaseservices.cnoe.io
spec:
  group: cnoe.io
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
              connectionStrings:
                type: string
              backupSchedules:
                type: string
              autoScaling:
                type: boolean
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
export OPENROUTER_MODEL="deepseek/deepseek-chat-v3.1:free"
```

Get your free API key from [OpenRouter.ai](https://openrouter.ai)

## Workflow

1. **Describe API**: Explain what you want in natural language
2. **Generate Spec**: AI creates OpenAPI 3.0 specification
3. **Deploy CRD**: Apply generated Kubernetes YAML
4. **Use Resource**: Interact with your new custom resource

Example deployment:
```bash
kubectl apply -f generated_specs/kubernetes/databaseservice-crd.yaml
kubectl get databaseservices.cnoe.io
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
