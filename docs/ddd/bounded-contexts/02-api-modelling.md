# Bounded Context — API Modelling

> **Purpose:** translate a validated **`CodegenRequest`** into the canonical
> **`OpenAPIDocument`** intermediate representation (IR) consumed by every
> downstream artefact generator.

This is a **core** subdomain. The IR is the single source of truth from
which every artefact is derived ([ADR-0004](../../adr/0004-openapi-3-as-intermediate-representation.md)).
Errors here propagate everywhere; correctness here is non-negotiable.

---

## 1. Responsibilities

1. Produce a deterministic, structural OpenAPI 3.0 document from a
   `CodegenRequest`.
2. Validate the produced document against:
   - OpenAPI 3.0 syntax.
   - Kubernetes' [structural-schema](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#specifying-a-structural-schema) rules.
   - Our own subset (no `oneOf` / `anyOf` / `additionalProperties: true`
     unless explicitly enabled by a future ADR).
3. Carry Kubernetes-specific extensions (`x-kubernetes-*`) where needed
   without leaking them back to the user-visible IR JSON.
4. Be **pure** — no IO, no clocks, no providers. Same input, same output.

This context **does not**:

- Talk to the LLM.
- Talk to the filesystem or cluster.
- Render any artefact (it produces the IR; rendering is the next context).

## 2. Ubiquitous language inside this context

Originated here: **OpenAPI IR**, **Spec Schema**, **Status Schema**,
**Structural Schema**, **JsonSchema**, **PathItem** (currently unused for
CRDs).

## 3. Aggregates and value objects

| Type                           | Pattern         | Notes                                                                  |
| ------------------------------ | --------------- | ---------------------------------------------------------------------- |
| `OpenAPIDocument`              | Aggregate root  | See `../04-tactical-design.md §4.2`.                                  |
| `OpenApiInfo`                  | Value object    | `(title, version, description, contact?, license?)`.                   |
| `JsonSchema`                   | Value object    | Recursive; supports the subset listed under §1.                        |
| `KindSchema` (specialisation)  | Value object    | The schema for the user's `Kind`; always has `apiVersion`, `kind`, `metadata`, `spec`, `status?`. |
| `KubernetesExtensions`         | Value object    | `(printer_columns, scale_subresource?, status_subresource_enabled, ...)`. |

## 4. Domain services

| Service                       | Responsibility                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| `IRBuilder`                   | Pure function `(CodegenRequest) -> OpenAPIDocument`.                                 |
| `StructuralSchemaValidator`   | Enforce Kubernetes structural-schema rules.                                          |
| `OpenApiSyntaxValidator`      | Enforce OpenAPI 3.0 syntax via `openapi_schema_validator` or equivalent.             |
| `IRSerialiser`                | Stable, sorted, deterministic JSON serialisation for the IR.                         |

## 5. Application service

`ApiModellingService` exposes:

```python
def build(self, request: CodegenRequest) -> OpenAPIDocument:
    """
    1. Build the IR via IRBuilder.
    2. Run StructuralSchemaValidator.
    3. Run OpenApiSyntaxValidator.
    4. On any violations: raise IRRejected.
    5. Emit IRConstructed event.
    """
```

## 6. Mapping rules: `CodegenRequest` → `OpenAPIDocument`

For a request `(group, version, kind, spec_properties, description)`:

```jsonc
{
  "openapi": "3.0.0",
  "info": {
    "title": "<Kind> API",
    "version": "<version>",
    "description": "<description>"
  },
  "paths": {},
  "components": {
    "schemas": {
      "<Kind>": {
        "type": "object",
        "required": ["apiVersion", "kind", "metadata", "spec"],
        "properties": {
          "apiVersion": { "type": "string", "description": "API version, e.g. <group>/<version>" },
          "kind":       { "type": "string", "description": "Resource kind, e.g. <Kind>" },
          "metadata":   { "type": "object", "properties": { "name": {"type": "string"}, "namespace": {"type": "string"} } },
          "spec": {
            "type": "object",
            "required": [ /* property names with `required: true` */ ],
            "properties": { /* one entry per SpecProperty */ }
          },
          "status": { "type": "object", "properties": {} }
        }
      }
    }
  }
}
```

Per-property mapping:

| `SpecProperty.type`   | OpenAPI mapping                                                                      |
| --------------------- | ------------------------------------------------------------------------------------ |
| `string`              | `{ "type": "string" }`                                                               |
| `integer`             | `{ "type": "integer", "format": "int32" }`                                           |
| `number`              | `{ "type": "number", "format": "double" }`                                           |
| `boolean`             | `{ "type": "boolean" }`                                                              |
| `array<X>`            | `{ "type": "array", "items": <map(X)>, "x-kubernetes-list-type": "atomic" }`         |
| `object`              | `{ "type": "object", "x-kubernetes-preserve-unknown-fields": false }`                |

Constraints (`PropertyConstraints`) are merged in:

| Constraint        | OpenAPI key            |
| ----------------- | ---------------------- |
| `minimum`         | `minimum`              |
| `maximum`         | `maximum`              |
| `min_length`      | `minLength`            |
| `max_length`      | `maxLength`            |
| `pattern`         | `pattern`              |
| `enum`            | `enum`                 |
| `format`          | `format`               |

Descriptions are propagated verbatim. Unspecified descriptions become
`Specification for <propName>` so the CRD always carries human help.

## 7. Determinism rules

Determinism is required for golden tests
([ADR-0018](../../adr/0018-test-pyramid-strategy.md)). Concretely:

- Property order in the emitted JSON is **lexicographic**, not insertion
  order.
- `required` arrays are sorted.
- Whitespace is fixed: 2-space indent, trailing newline.
- The `IRSerialiser` is the only path that produces serialised IR; nobody
  emits ad-hoc JSON.

## 8. Validation rules

`StructuralSchemaValidator` enforces:

1. Every level has an explicit `type`.
2. `properties` is used (not `additionalProperties` for arbitrary maps,
   except when explicitly opted in via constraints).
3. No `oneOf` / `anyOf` / `not` at the top level (Kubernetes restriction).
4. `default` values are JSON-schema-compatible with their `type`.
5. `description` is present on every named property.

Failure produces an `IRRejected` error with a list of `FieldViolation`s.

## 9. Domain events emitted

| Event              | When                                                            |
| ------------------ | --------------------------------------------------------------- |
| `IRConstructed`    | After successful build + validation.                            |
| `IRRejected`       | When validation produces violations.                            |

## 10. Failure modes

| Failure                                    | Outcome                                                  |
| ------------------------------------------ | -------------------------------------------------------- |
| Unknown `PropertyType`                     | Caller bug — terminal.                                   |
| Conflicting `PropertyConstraints` + `type` | Caller bug — terminal.                                   |
| Structural-schema violation                | `IRRejected` with violations.                            |
| Reserved Kubernetes group used             | `IRRejected` with code `E_API_RESERVED_GROUP`.           |

## 11. Public contract

Inputs:

- A valid `CodegenRequest` aggregate (already past Intent Interpretation
  validation).

Output:

- `OpenAPIDocument` aggregate, which is also serialisable via
  `IRSerialiser.dump_json`.

## 12. Testing strategy

- **Unit:** every mapping rule (one test per `PropertyType` ×
  `PropertyConstraints` combination).
- **Property:** random valid `CodegenRequest`s produce IR that round-trips
  through `IRSerialiser` byte-stable.
- **Golden:** the eight canonical scenarios listed in
  [`../08-implementation-roadmap.md`](../08-implementation-roadmap.md)
  produce checked-in IR snapshots.

## 13. Future work

- OpenAPI 3.1 migration (when Kubernetes accepts it).
- Conversion-webhook generation for multiple stored versions.
- `oneOf` / `anyOf` support for advanced schemas.
- Printer columns inferred from the request when the user asks for them.
