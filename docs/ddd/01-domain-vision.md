# 01 — Domain Vision

## Mission

> Compress the time between *"I have an idea for a platform API"* and *"That
> API is running in a Kubernetes cluster"* from days to minutes, while
> producing artefacts that an experienced platform engineer would be willing
> to merge unchanged.

## Problem statement

Building a new Kubernetes-native API today involves:

1. Choosing a `group` / `version` / `kind` triple that does not collide with
   existing CRDs.
2. Writing a structural OpenAPI v3 schema for the resource.
3. Authoring the CRD YAML with the right `served` / `storage` / printer
   columns / additional printer columns.
4. Optionally scaffolding a Go controller (`kubebuilder init`,
   `kubebuilder create api`, custom types, reconciler stub, RBAC markers,
   Dockerfile).
5. Deploying everything to a test cluster, applying a sample instance, and
   confirming that `kubectl get` works.

Each step is mechanical, error-prone, and requires Kubernetes-API
expertise. Junior engineers cannot do it without supervision; senior
engineers find it tedious. Mistakes propagate (a bad schema is hard to
evolve once data exists in clusters).

## Why now

Three forces converge to make the project worthwhile:

- **LLMs reliably translate intent into structured outputs** when
  constrained by a strict system prompt and JSON schema.
- **Kubernetes has standardised on OpenAPI v3 schema** for CRDs, so the
  output of an AI is directly consumable.
- **Platform-engineering teams are building "internal developer
  platforms"** at scale and are bottlenecked on API authoring.

## Vision

A single command — natural-language in, running CRD out — that:

- **Hides nothing.** Every artefact is human-readable, diffable, and lives
  in the user's filesystem under their control. There is no opaque service
  call.
- **Defaults to safety.** Generated controllers ship as distroless,
  non-root, RBAC-scoped. Generated CRDs ship as `v1alpha1` with a clear
  promotion path.
- **Works offline.** Users on flights and in air-gapped CI still get a
  representative output (Demo Mode) and can iterate on the surrounding
  infrastructure.
- **Is honest about uncertainty.** When the AI is guessing, the tool says
  so. When fields are inferred rather than specified, the manifest records
  it.

## Target users

| Persona                 | Goal                                                                            | Pain today                                                              |
| ----------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Platform engineer**   | Build new internal APIs (DatabaseService, CacheCluster, MLPipeline) on demand   | Each new API is a multi-day yak-shave through kubebuilder boilerplate   |
| **Application developer** | Get a CRD that exposes "the abstraction my team needs" without learning Kubernetes deeply | Kubernetes API authoring is gatekept by the platform team             |
| **Developer-experience lead** | Standardise API patterns across teams                                       | Every team invents its own conventions                                  |
| **Conference / sales engineer** | Demonstrate AI-native infra in 90 seconds                                | Live demos depend on the network and on prompt luck                     |

## Success metrics

- **Time to a deployed CRD**: < 3 minutes including cluster startup.
- **Generated artefact fidelity**: ≥ 95 % of generated CRDs deploy without
  manual edit on the first attempt.
- **Demo-mode success rate**: 100 % — `./run.sh demo` always finishes,
  online or offline.
- **Onboarding**: a contributor can ship a new artefact generator in a day,
  guided by `docs/ddd/` alone.

## Out of scope (for now)

- Reconciler *business logic*. The generator scaffolds; the user owns
  reconciliation.
- Multi-cluster lifecycle management.
- Database / state migrations for CRD schema evolution.
- Building a SaaS hosted version.

## Domain narrative

> A platform engineer named **Alex** is asked to expose a managed-Postgres
> service to her company's internal teams. She types:
>
> ```
> Create a PostgresCluster API with replicas (int 1-7), storageGiB (int),
> backupSchedule (cron string), and tlsEnabled (bool).
> ```
>
> The generator parses Alex's intent into a `CodegenRequest` (Intent
> Interpretation context), translates it into an OpenAPI 3.0 IR (API
> Modelling), and from that single IR produces:
>
> - A CRD `postgresclusters.database.cnoe.io/v1alpha1`.
> - A sample `PostgresCluster` instance.
> - A Go controller scaffold (Artifact Generation).
>
> The Cluster Provisioning context spins up a Kind cluster, applies the
> CRD, applies the sample instance, and confirms that
> `kubectl get postgresclusters` returns Alex's resource. All of this is
> rendered in the User Interaction context as a Rich-styled progress
> stream, and every step emits a domain event captured by the
> Observability context.
>
> Three minutes later Alex copies `generated_specs/postgrescluster/` into
> her platform monorepo, opens a PR, and starts implementing the
> reconciler.

This narrative is the canonical example used throughout the documentation,
implementation, and golden-file tests
([ADR-0018](../adr/0018-test-pyramid-strategy.md)).
