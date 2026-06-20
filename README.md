# Cogni Life OS

**A sovereign, local-first personal AI system built on an Obsidian-compatible Markdown vault.**

Cogni Life OS captures information, preserves original sources, retrieves relevant knowledge, and coordinates bounded AI-assisted actions without making a cloud database the owner of your memory.

Markdown remains the source of truth. Search indexes and runtime caches are disposable and rebuildable.

## Why Cogni Life OS

Most personal AI systems place your memory, context, and automation inside proprietary cloud services.

Cogni Life OS is designed around a different model:

* your knowledge remains in readable Markdown;
* original sources and provenance are preserved;
* AI actions are validated before they modify the vault;
* retrieval runs locally;
* model inference can run on your own hardware;
* indexes can be deleted and rebuilt without losing knowledge.

## Features

* Obsidian-compatible Markdown vault
* Text, image, PDF, DOCX, receipt, screenshot, and audio ingestion
* Source preservation with hashes and provenance
* Durable tasks with restart recovery and idempotency
* Typed tools and bounded write plans
* Atomic writes with conflict detection
* Local full-text and layered retrieval
* Rebuildable SQLite indexes
* Local Cogni-Brain integration
* Authenticated loopback HTTP API
* Backup, restore, integrity, and soak testing
* No LangChain, LangGraph, LiteLLM, or cloud AI dependency

## Architecture

```text
CLI / Local API
       |
       v
Cogni Life OS
       |
       +-- Source preservation
       +-- Durable tasks
       +-- Policy and tool validation
       +-- Retrieval and ranking
       +-- Backup and integrity
       |
       +-- Markdown vault
       |
       +-- Local Cogni-Brain endpoint
```

The Markdown vault and preserved attachments are authoritative.

SQLite databases, retrieval indexes, caches, generated evidence, and benchmark corpora are disposable runtime artifacts.

## Quick Start

### Requirements

* Python 3.9+
* macOS or Linux
* access to an OpenAI-compatible local model endpoint

Optional extraction tools:

* Tesseract for OCR
* PyMuPDF for PDF extraction
* whisper-cpp for audio transcription

### Install

```bash
git clone https://github.com/airawatraj/cogni-life-os.git
cd cogni-life-os
./scripts/install.sh
```

### Configure

Copy the example environment file:

```bash
cp .env.example .env
```

Example local configuration:

```bash
export COGNI_MODEL_BASE_URL="http://127.0.0.1:8000/v1"
export COGNI_MODEL_API_KEY="local"
export COGNI_SERVICE_TOKEN="replace-with-a-strong-random-token"
```

`COGNI_MODEL_API_KEY=local` is a compatibility placeholder for local OpenAI-compatible endpoints.

`COGNI_SERVICE_TOKEN` protects access to the Cogni Life OS API and should be a strong random value.

### Start

```bash
./scripts/start.sh
```

The service binds to loopback by default.

### Capture a note

```bash
python3 -m cogni_life_os capture-text \
  "Remember to renew insurance next week"
```

## Commands

Run tests:

```bash
./scripts/test.sh
```

Run the complete local evaluation suite:

```bash
./scripts/evaluate.sh
```

Rebuild disposable indexes:

```bash
./scripts/index-rebuild.sh
```

Run vault integrity checks:

```bash
./scripts/integrity.sh
```

Create a backup:

```bash
./scripts/backup.sh
```

Restore and verify a backup:

```bash
./scripts/restore.sh
```

List available CLI commands:

```bash
python3 -m cogni_life_os --help
```

## Safety Model

Cogni-Brain does not receive unrestricted write access.

```text
model proposal
    -> schema validation
    -> evidence validation
    -> policy checks
    -> bounded write plan
    -> atomic write
    -> read-back verification
    -> audit record
```

Unsafe, unsupported, or insufficiently evidenced actions fail closed.

The local API:

* binds to loopback by default;
* requires authentication;
* rejects path traversal and symlink escapes;
* validates uploads and filenames;
* limits model tool permissions;
* supports pause and kill-switch controls.

## Storage Model

```text
local_test_vault/
├── 00-system/
├── 10-sources/
├── 20-entities/
├── 30-concepts/
├── 40-projects/
├── 50-actions/
├── 60-decisions/
└── 70-synthesis/
```

The included `local_test_vault` is disposable development data.

Do not point an unreviewed build at a personal or production vault.

## Project Status

Cogni Life OS currently provides a local-only implementation with:

* source preservation;
* durable task state;
* multimodal extraction;
* local retrieval;
* Cogni-Brain integration;
* an authenticated local API;
* backup and restore;
* integrity and resource testing.

The following remain separate deployment milestones:

* iCloud vault integration
* physical iPhone validation
* private remote access
* real cross-device conflict testing
* production-vault activation

## Verification

Run the local test and evaluation suite:

```bash
./scripts/test.sh
./scripts/evaluate.sh
```

## Documentation

Additional architecture and operating documentation is available under [`docs/`](docs/).
