# GitHub Integration

## Configuration

Add `.incident-ci.yaml` to the repository:

```yaml
schema_version: 1
required_labels:
  - incident
exempt_labels:
  - incident-card-exempt
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services:
  - payment-api
  - auth-api
  - order-api
```

Add new services by appending lowercase kebab-case names to `allowed_services`.

## Workflow

```yaml
name: Incident Card

on:
  pull_request:
    types:
      - opened
      - edited
      - synchronize
      - labeled
      - unlabeled

permissions:
  contents: read
  pull-requests: read
  security-events: write

jobs:
  incident-card:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Build changed file list
        run: |
          git diff --name-only --diff-filter=AM \
            "${{ github.event.pull_request.base.sha }}" \
            "${{ github.event.pull_request.head.sha }}" > changed-files.txt

      - name: Install incident-ci
        run: uv sync --frozen

      - name: Validate Incident Card
        run: |
          uv run incident-ci check \
            --config .incident-ci.yaml \
            --files-from changed-files.txt \
            --labels "${{ join(github.event.pull_request.labels.*.name, ',') }}" \
            --format sarif \
            --output incident-ci.sarif

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: incident-ci.sarif
          category: incident-card
```

For production repositories, pin third-party actions to commit SHAs.

## Local CLI

Validate one file:

```bash
uv run incident-ci check incidents/INC-2026-001.md --config .incident-ci.yaml
```

Validate a changed-file list and write SARIF:

```bash
uv run incident-ci check \
  --config .incident-ci.yaml \
  --files-from changed-files.txt \
  --labels incident \
  --format sarif \
  --output incident-ci.sarif
```

## SARIF Results

The CLI writes SARIF 2.1.0. GitHub displays uploaded SARIF results as code scanning alerts and inline
annotations on real files from the pull request head commit.
