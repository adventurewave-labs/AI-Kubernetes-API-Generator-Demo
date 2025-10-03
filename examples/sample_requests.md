# Sample Requests for AI Platform Extension Generator

This document contains example natural language requests that you can use with the AI platform extension generator.

## Basic Examples

### 1. Vector Database API
**Request**: "Create a VectorDB API for our AI platform. It should have engine_type (string) for different providers like 'pinecone' or 'weaviate', replicas (integer) for number of instances, and storage_size (string) for persistent storage."

**Expected Output**:
- Kind: VectorDB
- Group: platform.ai.cnoe.io (inferred)
- Version: v1alpha1 (default)
- Spec Properties:
  - engine_type: string
  - replicas: integer
  - storage_size: string

### 2. Cache Cluster
**Request**: "I need a CacheCluster for our microservices. Include size (string) for cache size like 'small', 'medium', 'large', memory (string) for memory allocation, and port (integer) for the cache port."

**Expected Output**:
- Kind: CacheCluster
- Group: platform.cnoe.io (default)
- Version: v1alpha1 (default)
- Spec Properties:
  - size: string
  - memory: string
  - port: integer

### 3. Database Backup Resource
**Request**: "Build a DatabaseBackup resource with schedule (string) for cron schedule, retention_days (integer) for backup retention, and enabled (boolean) to enable/disable backups."

**Expected Output**:
- Kind: DatabaseBackup
- Group: platform.cnoe.io (default)
- Version: v1alpha1 (default)
- Spec Properties:
  - schedule: string
  - retention_days: integer
  - enabled: boolean

## Advanced Examples

### 4. Configuration Template
**Request**: "Create a ConfigTemplate resource that helps manage application configurations. It should have template_name (string), variables (object) for template variables, namespace (string) for target namespace, and version (string) for template version."

**Expected Output**:
- Kind: ConfigTemplate
- Group: config.cnoe.io
- Version: v1alpha1
- Spec Properties:
  - template_name: string
  - variables: object
  - namespace: string
  - version: string

### 5. Service Mesh Route
**Request**: "I need a MeshRoute for our service mesh. Include service_name (string), target_service (string), weight (integer) for load balancing, and headers (object) for custom headers."

**Expected Output**:
- Kind: MeshRoute
- Group: mesh.cnoe.io
- Version: v1alpha1
- Spec Properties:
  - service_name: string
  - target_service: string
  - weight: integer
  - headers: object

### 6. Pipeline Resource
**Request**: "Create a Pipeline resource for CI/CD automation. Include stages (array) of pipeline stages, repository_url (string) for git repo, branch (string) for target branch, and triggers (object) for pipeline triggers."

**Expected Output**:
- Kind: Pipeline
- Group: ci.cnoe.io
- Version: v1alpha1
- Spec Properties:
  - stages: array
  - repository_url: string
  - branch: string
  - triggers: object

## Testing with the CLI

### Interactive Mode
```bash
# Start interactive mode
ai-platform-gen interactive

# Then enter any of the requests above
```

### Direct Generation
```bash
# Generate and display parsed request
ai-platform-gen generate "Create a VectorDB API with engine_type and replicas"

# Generate specific output directory
ai-platform-gen generate "Build a CacheCluster with size and memory" --output-dir ./my-cache-cluster

# Use JSON output format
ai-platform-gen generate "Create a DatabaseBackup with schedule and retention" --format json
```

### Build from Saved Request
```bash
# Save a request to JSON file
ai-platform-gen generate "Create a VectorDB API" --format json > vectordb-request.json

# Build the actual code
ai-platform-gen build vectordb-request.json --output-dir ./generated-vectordb
```

## Request Patterns

### Effective Request Patterns
1. **Start with the resource type**: "Create a X resource..." or "I need a X API..."
2. **Clearly specify fields**: "...with field1 (type1) and field2 (type2)"
3. **Provide context**: "...for our microservices" or "...for AI workloads"
4. **Use standard types**: string, integer, boolean, array, object

### Type Inference
The AI will automatically infer types from context:
- Numbers → integer
- Text values → string
- true/false → boolean
- Lists → array
- Key-value pairs → object

### Default Values
- Group: platform.cnoe.io (unless specified)
- Version: v1alpha1 (unless specified)
- Output Directory: /tmp/{kind} (unless specified)

## Tips for Better Requests

1. **Be specific about field types**: "port (integer)" instead of just "port"
2. **Provide context for the resource**: "for AI platform" or "for caching"
3. **Use consistent naming**: CamelCase for resource names
4. **Group related fields**: Mention related functionality together

## Troubleshooting

### Common Issues
- **Invalid kind names**: Use CamelCase (VectorDB, not vectordb)
- **Missing types**: Always specify field types in parentheses
- **Vague descriptions**: Provide specific field requirements

### Validation Errors
If you get validation errors:
1. Check that resource kind is CamelCase
2. Ensure all field types are specified
3. Verify at least one spec property is included
4. Make sure the request is clear and unambiguous