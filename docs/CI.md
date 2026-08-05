# Running CI for this repo

Automatic workflow triggers in this repository are **gated**: pushing does not
start a GitHub-hosted run any more. Checks run on local hardware, and the
workflows that remain are started deliberately.

Why: GitHub Actions was costing the org $563/month, almost all of it hosted
compute for checks that run just as well on hardware we already own.

Starting a gated workflow needs the [`gh` CLI](https://cli.github.com) and push
access. `--ref` matters - the workflow file is read from that branch, so a
workflow that only exists on your feature branch must be dispatched against it.

Full cross-repo runbook: `CI-Local-CICD/RUNBOOK.md` (regenerate with
`ci-local docs`). This file is generated - do not hand-edit.

---

Default branch: `main`

### Test locally

_No local checks detected._

### Run a check workflow on GitHub

**Entelligence-AI** — `entellegence_issues.yml`

```bash
gh workflow run entellegence_issues.yml --repo companionintelligence/CI-OMI --ref main
```

**Code Review** — `entelligence-pr-reviewer.yml`

```bash
gh workflow run entelligence-pr-reviewer.yml --repo companionintelligence/CI-OMI --ref main
```

**Deploy Apps-Js to Cloud RUN** — `gcp_apps_js.yml`

```bash
gh workflow run gcp_apps_js.yml --repo companionintelligence/CI-OMI --ref main -f environment=development -f branch=main
```

Required inputs: `environment` (Select the environment to deploy to), `branch` (Branch to deploy from)

**Deploy Backend to Cloud RUN** — `gcp_backend.yml`

```bash
gh workflow run gcp_backend.yml --repo companionintelligence/CI-OMI --ref main -f environment=development -f branch=main
```

Required inputs: `environment` (Select the environment to deploy to), `branch` (Branch to deploy from)

**Deploy Backend Pusher to Cloud RUN** — `gcp_backend_pusher.yml`

```bash
gh workflow run gcp_backend_pusher.yml --repo companionintelligence/CI-OMI --ref main -f environment=development -f branch=main
```

Required inputs: `environment` (Select the environment to deploy to), `branch` (Branch to deploy from)

**Deploy Frontend to Cloud RUN** — `gcp_frontend.yml`

```bash
gh workflow run gcp_frontend.yml --repo companionintelligence/CI-OMI --ref main -f branch=main
```

Required inputs: `branch` (Branch to deploy from)

**Deploy Speech Models to Cloud RUN** — `gcp_models.yml`

```bash
gh workflow run gcp_models.yml --repo companionintelligence/CI-OMI --ref main -f environment=development -f branch=main
```

Required inputs: `environment` (Select the environment to deploy to), `branch` (Branch to deploy from)

**Deploy Notifications Job to Cloud RUN** — `gcp_notifications_job.yml`

```bash
gh workflow run gcp_notifications_job.yml --repo companionintelligence/CI-OMI --ref main -f environment=development -f branch=main
```

Required inputs: `environment` (Select the environment to deploy to), `branch` (Branch to deploy from)

**Deploy Personas to Cloud RUN** — `gcp_personas.yml`

```bash
gh workflow run gcp_personas.yml --repo companionintelligence/CI-OMI --ref main -f branch=main
```

Required inputs: `branch` (Branch to deploy from)

**Deploy Plugins to Cloud RUN** — `gcp_plugins.yml`

```bash
gh workflow run gcp_plugins.yml --repo companionintelligence/CI-OMI --ref main
```

**GitHub Issue Sync** — `main.yml`

```bash
gh workflow run main.yml --repo companionintelligence/CI-OMI --ref main -f excludeClosed=true
```

**Sync Mintlify Docs back to Github** — `sync-docs.yml`

```bash
gh workflow run sync-docs.yml --repo companionintelligence/CI-OMI --ref main
```

### Cut a release

**Deploy static content to Pages** — `deploy_docs.yml`

```bash
gh workflow run deploy_docs.yml --repo companionintelligence/CI-OMI --ref main
```
