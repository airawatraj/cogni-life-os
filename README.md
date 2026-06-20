# Cogni Life OS

Cogni Life OS is a sovereign, local-first personal knowledge and automation system built around an Obsidian-compatible Markdown vault.

The Markdown vault is the canonical source of truth. Search indexes, caches, queues, and runtime databases are disposable and must be rebuildable from the vault.

This repository currently implements and verifies the local-only phase using a fresh disposable vault inside the project.

## Current Scope

Included in this phase:

* local disposable Markdown vault;
* text and binary source preservation;
* Obsidian-compatible notes, frontmatter, and wiki links;
* safe path handling and atomic writes;
* deterministic proposal validation;
* durable task and operation state;
* local multimodal extraction;
* disposable SQLite full-text indexing;
* retrieval evaluation at 10k, 50k, and 100k notes;
* backup and restore;
* integrity checking;
* local authenticated HTTP API;
* direct Cogni-Brain integration;
* automated deterministic, live-model, multimodal, retrieval, and soak evaluations.

Deferred external gates:

* iCloud integration testing;
* production iCloud vault activation;
* physical iPhone validation;
* remote private transport;
* cross-device conflict testing.

Do not point this repository state at a real personal or production vault.

## Architecture

```text
Local CLI / HTTP API
       |
       v
Local Cogni Life OS service
       |
       +--> Source preservation
       +--> Durable task state
       +--> Typed tools
       +--> Deterministic policy and write plans
       +--> Disposable retrieval indexes
       |
       +--> Obsidian-compatible Markdown vault
       |
       +--> local Cogni-Brain endpoint
```

### Source of truth

Authoritative data is stored in Markdown and preserved attachments.

Disposable runtime state may include:

* SQLite full-text indexes;
* retrieval caches;
* temporary files;
* evaluation corpora;
* generated reports.

Deleting disposable indexes must not remove durable knowledge, provenance, task state, or audit history.

## Repository Layout

```text
cogni_life_os/
├── cogni_life_os/          # Application package
├── scripts/                # Install, run, test, and evaluation commands
├── tests/                  # Deterministic and integration tests
├── docs/                   # Architecture and operating documentation
├── local_test_vault/       # Disposable local development vault
├── .cogni/
│   ├── runtime/            # Disposable indexes and runtime state
│   ├── backups/            # Local backup archives
│   └── local-*evidence*/   # Generated evaluation evidence
├── pyproject.toml
└── README.md
```

Generated vault contents, runtime databases, models, backups, secrets, and evidence archives should not be committed to Git.

## Requirements

* macOS or Linux
* Python 3.9 or newer
* access to the local Cogni-Brain endpoint
* optional local extraction dependencies:

  * Tesseract for OCR;
  * PyMuPDF for PDF extraction;
  * whisper-cpp or the configured local transcription engine;
  * DOCX extraction dependencies.

The installation script validates required and optional dependencies.

## Installation

```bash
./scripts/install.sh
```

Activate the environment if the installer creates one:

```bash
source .venv/bin/activate
```

## Configuration

Default configuration is defined in:

```text
cogni_life_os/config.py
```

Important defaults:

| Setting              | Default                        |
| -------------------- | ------------------------------ |
| Development vault    | `local_test_vault`             |
| Runtime directory    | `.cogni/runtime`               |
| Backup directory     | `.cogni/backups`               |
| Cogni-Brain endpoint | `http://192.168.20.91:8000/v1` |
| Cogni-Brain API key  | `local`                        |
| Service bind address | `127.0.0.1`                    |

Sensitive values should be supplied through environment variables or local configuration excluded from Git.

Example:

```bash
export COGNI_SERVICE_TOKEN="replace-with-a-strong-local-token"
export COGNI_MODEL_BASE_URL="http://192.168.20.91:8000/v1"
export COGNI_MODEL_API_KEY="local"
```

The service must refuse unsafe configuration rather than silently using default credentials.

## Start the Local Service

```bash
./scripts/start.sh
```

The service binds to loopback by default:

```text
http://127.0.0.1:<configured-port>
```

This phase is local-only. Do not expose the service to the LAN or internet.

## CLI Usage

Capture a text source:

```bash
python3 -m cogni_life_os capture-text \
  "Remember to renew insurance next week"
```

Other commands can be listed with:

```bash
python3 -m cogni_life_os --help
```

## Core Commands

Install dependencies:

```bash
./scripts/install.sh
```

Start the local service:

```bash
./scripts/start.sh
```

Run deterministic tests:

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

Run live Cogni-Brain evaluations:

```bash
./scripts/live-model-test.sh
```

Run retrieval evaluation:

```bash
./scripts/retrieval-eval.sh
```

Run the soak test:

```bash
./scripts/soak-test.sh
```

Create a local backup:

```bash
./scripts/backup.sh
```

Restore and verify a local backup:

```bash
./scripts/restore.sh
```

## Vault Structure

The disposable local vault may contain:

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

### Sources

Every source is preserved before interpretation.

Source records include:

* immutable source ID;
* original content or attachment;
* cryptographic hash;
* received timestamp;
* detected MIME type;
* extraction status;
* extraction method;
* provenance;
* links to derived records.

### Tasks and operations

Durable task records track:

* task phase;
* current step;
* attempts;
* operation IDs;
* retries;
* checkpoints;
* completed side effects;
* final status;
* quarantine reasons.

### Proposals and writes

Cogni-Brain does not receive unrestricted write access.

The expected flow is:

```text
model proposal
    -> schema validation
    -> evidence validation
    -> policy and autonomy checks
    -> bounded write plan
    -> expected-hash verification
    -> atomic write
    -> read-back verification
    -> audit record
```

Unknown, unsafe, or insufficiently supported proposals fail closed.

## Retrieval

Retrieval uses disposable local indexes built from Markdown.

Supported retrieval signals may include:

* title;
* aliases;
* frontmatter;
* tags;
* full text;
* entities;
* concepts;
* dates;
* wiki links;
* backlinks;
* domain and recency weighting.

Normal queries must not scan the entire vault.

Indexes can be deleted and rebuilt without losing authoritative information.

## Multimodal Processing

The local extraction pipeline can support:

* photographs;
* screenshots;
* receipts;
* text PDFs;
* scanned PDFs;
* DOCX files;
* WAV or supported audio.

Each extractor returns a typed result containing:

* status;
* extracted text;
* detected MIME type;
* extractor name and version;
* confidence where available;
* warnings;
* error code;
* timeout state;
* source hash.

Unsupported formats fail closed.

Video understanding is not considered verified unless explicitly supported by the current evidence.

## Cogni-Brain Integration

The local model service is accessed directly without LangChain, LangGraph, LiteLLM, AnythingLLM, or cloud AI.

Default endpoint:

```text
http://192.168.20.91:8000/v1
```

The client must handle:

* normal text responses;
* tool calls;
* `content: null`;
* reasoning-only responses;
* `reasoning_content`;
* malformed JSON;
* truncated output;
* retries;
* timeouts;
* endpoint failures;
* bounded continuation.

Live model capability is determined by executed evaluation evidence, not by model marketing claims.

## Security

Current local security controls include:

* loopback-only binding;
* required authentication token;
* refusal of unsafe default credentials;
* path traversal protection;
* symlink escape protection;
* upload-size limits;
* MIME inspection;
* filename sanitisation;
* deterministic tool permissions;
* no unrestricted shell or filesystem access for the model;
* pause and kill-switch controls;
* safe logging and secret redaction.

This repository state is not approved for LAN exposure, internet exposure, or physical iPhone access.

## Testing and Evidence

The project distinguishes between:

* deterministic tests;
* mocked tests;
* local-tool integration tests;
* live Cogni-Brain tests;
* retrieval benchmarks;
* soak and resource tests;
* deferred external gates.

A skipped or unavailable test must not be counted as passed.

Generated evidence should record:

* requirement ID;
* test ID;
* expected result;
* actual result;
* pass, fail, skip, or deferred status;
* command;
* timestamp;
* code version;
* model and endpoint where applicable;
* evidence path.

## Backup and Restore

Backups must include durable vault data and preserved attachments.

A valid backup is not considered verified until it has been restored into an empty destination and checked for:

* file hashes;
* attachment hashes;
* source IDs;
* frontmatter validity;
* broken links;
* missing files;
* index rebuild;
* representative retrieval equivalence.

Use the documented backup and restore commands under `scripts/`.

## Current Status

Local readiness should be claimed only when all local gates pass, including:

* deterministic tests;
* security tests;
* source preservation;
* durable restart and idempotency;
* backup and restore;
* real multimodal fixtures;
* realistic retrieval at 10k, 50k, and 100k notes;
* repeated live Cogni-Brain thresholds;
* resource-leak checks;
* meaningful soak testing.

The following remain outside this phase:

```text
DEFERRED_EXTERNAL_GATE
```

* iCloud integration;
* production vault activation;
* physical iPhone use;
* encrypted remote access;
* real cross-device conflict testing.

## Development Rules

* Keep Markdown authoritative.
* Keep indexes disposable.
* Never commit secrets or personal vault data.
* Never test against the production vault.
* Do not mark skipped tests as passed.
* Do not claim production, iCloud, iPhone, remote-network, video, live multimodal, or semantic-retrieval support without raw evidence.
* Use Conventional Commits.

Examples:

```text
feat(retrieval): add layered local ranking
fix(model): handle truncated reasoning responses
test(agent): cover crash recovery and idempotency
docs: update local deployment guide
chore: refresh repository hygiene
```

## Licence

Add the project licence here when selected.
