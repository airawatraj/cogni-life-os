# Cogni Life OS — Final Production Requirements

## 1. Mission

Build a sovereign, transparent, scalable, autonomous Life OS that uses:

- `Cogni-Brain` on the NVIDIA DGX Spark for reasoning and multimodal interpretation;
- an Obsidian-compatible Markdown vault as the canonical source of truth;
- a private PWA for iPhone and MacBook Pro;
- a local Python service for ingestion, orchestration, retrieval, validation, and safe writes.

The system must handle a continuous firehose of digital information across:

- personal life;
- family;
- work;
- administration;
- relationships;
- learning;
- modern knowledge;
- ancient knowledge;
- decisions;
- goals;
- projects;
- ideas;
- long-term creative and intellectual outputs.

The system must minimise manual review and must not create another inbox that requires constant triage.

## 2. Existing Environment

### Model service

- Hardware: NVIDIA DGX Spark
- Served model: `Cogni-Brain`
- Endpoint: `http://192.168.20.91:8000/v1`
- API key: `local`

### User devices

- MacBook Pro
- iPhone
- Obsidian

### Important model-contract rule

The exact behaviour of the served endpoint must be verified before implementation assumptions are made.

The implementation must live-test:

- text;
- image understanding;
- OCR;
- audio understanding or transcription;
- video understanding;
- tool calling;
- `content`;
- `reasoning`;
- `reasoning_content`;
- long-context behaviour;
- timeout behaviour;
- failure behaviour.

Do not claim a capability merely because the underlying model advertises it.

## 3. Non-Negotiable Principles

### 3.1 Sovereignty

- Core processing remains local.
- No cloud AI is required.
- No hosted database is required.
- No SaaS workflow platform is required.
- The user owns all durable data in readable and portable formats.
- The system must remain usable without a vendor account.

### 3.2 Transparency

- The Obsidian-compatible Markdown vault is the canonical source of truth.
- Durable knowledge and important operational state must be visible in Markdown.
- Every derived result must identify:
  - source;
  - evidence;
  - confidence;
  - uncertainty;
  - whether it is fact, user-authored text, model inference, tentative interpretation, or synthesis;
  - creation and update history.
- No essential state may exist only in an opaque database.

### 3.3 Human–LLM Co-Editing

- The user and the harness must safely edit the same vault.
- Manual Obsidian edits must be preserved.
- The system must detect changed files before writing.
- Conflicts must create explicit conflict records instead of silent overwrites.
- The vault must remain useful when the service is not running.

### 3.4 Scalability

The system must support at least:

- 10,000 notes for the initial production gate;
- 50,000 notes for the scale gate;
- 100,000 notes for the stress gate.

Normal queries must not:

- scan every Markdown file;
- load the entire vault into context;
- rewrite large portions of the vault;
- create uncontrolled note growth.

All indexes must be:

- incremental;
- disposable;
- rebuildable from the vault;
- non-authoritative.

### 3.5 Reliability

- Every task must be traceable.
- Writes must be atomic and read-back verified.
- Duplicate inputs must not create duplicate outputs.
- Interrupted tasks must resume safely or quarantine.
- Unknown or ambiguous cases must not be silently guessed.
- Failures must be visible and recoverable.

## 4. Required Environment Separation

The system must use three strictly separated vault environments.

### 4.1 Development vault

Purpose:

- implementation;
- unit testing;
- synthetic data;
- parser and tool testing;
- local scale testing;
- destructive testing.

Requirements:

- stored locally on the MacBook Pro;
- not in iCloud;
- disposable;
- must contain no production personal data;
- must never point to the production vault.

### 4.2 iCloud integration test vault

Purpose:

- iCloud sync testing;
- concurrent edit testing;
- delayed download testing;
- conflict testing;
- duplicate event testing;
- rename/move testing;
- interrupted write testing;
- attachment sync testing.

Requirements:

- separate disposable Obsidian vault in iCloud Drive;
- synthetic or sanitised data only;
- clearly named as non-production;
- safe to delete and recreate;
- must never contain the real production knowledge base.

### 4.3 Production iCloud vault

Purpose:

- real long-term Life OS;
- human and LLM co-editing;
- real personal, family, work, and knowledge data.

Requirements:

- must not be created, modified, or migrated during development;
- may only be enabled after all critical production gates pass;
- must require explicit user approval before activation;
- must start with backups enabled;
- must start with conservative write limits;
- must support rollback;
- migration must be staged and reversible.

The implementation must never use the real production iCloud vault as a development or test environment.

## 5. Core Architecture

```text
iPhone / MBP private PWA
        ↓
Local Python Cogni service on MBP
        ↓
Bounded agent loop + typed tools
        ↓
Obsidian Markdown vault
        ↓
Cogni-Brain on DGX Spark
```

Optional:

- a small Obsidian plugin for in-vault chat, commands, health, provenance, and diagnostics;
- local OCR and transcription binaries;
- rebuildable local search indexes outside the vault.

The core system must not depend on AnythingLLM.

## 6. Canonical Storage Rules

The vault must contain durable representations of:

- sources;
- attachments;
- entities;
- aliases;
- concepts;
- relationships;
- wiki links;
- people context;
- actions;
- duties;
- risks;
- commitments;
- decisions;
- events;
- insights;
- claims;
- contradictions;
- questions;
- projects;
- outputs;
- task state;
- processing history;
- validation outcomes;
- quarantine records;
- provenance;
- audit history;
- dashboards;
- health indicators.

A local database or index may be used only for:

- locks;
- queue coordination;
- idempotency keys;
- temporary caches;
- rebuildable search indexes;
- crash recovery.

Any such store must be:

- non-authoritative;
- disposable;
- rebuildable from the vault;
- never the only location of important state.

## 7. iCloud Safety Requirements

The implementation must account for real iCloud behaviour.

Required safeguards:

- atomic temp-file plus rename writes;
- pre-write and post-write hashes;
- read-back verification;
- file-stability checks before processing;
- detection of placeholders and partially downloaded files;
- retry on temporary iCloud unavailability;
- conflict copies on concurrent edits;
- no silent overwrite;
- immutable source IDs;
- immutable operation IDs;
- repeated file-event suppression;
- moved or renamed note reconciliation;
- missing attachment detection;
- incomplete-write detection;
- broken-link detection;
- duplicate-ID detection;
- one-command integrity scan.

Generated caches should remain outside the iCloud vault where practical.

Local file locks may be used only as local coordination hints. They must not be treated as cross-device iCloud locks.

## 8. User Interface

### 8.1 Private PWA

The PWA must support:

- natural-language chat;
- text capture;
- camera capture;
- image upload;
- screenshot upload;
- PDF and document upload;
- audio recording;
- voice-note upload;
- video upload where supported;
- link capture;
- task status;
- citations;
- vault links;
- minimal traffic-light dashboard;
- quarantine and conflict alerts;
- vault search and question answering.

### 8.2 Security

The PWA must:

- bind locally by default;
- require authenticated private access;
- keep model credentials server-side;
- use encrypted transport for remote iPhone access;
- enforce upload limits;
- validate MIME types;
- prevent path traversal;
- protect against CSRF;
- support session revocation;
- log security-relevant events;
- never expose an unauthenticated LAN service.

### 8.3 Optional Obsidian Plugin

An optional plugin may provide:

- process current note;
- process selected text;
- ask vault;
- show provenance;
- explain note;
- show task health;
- rebuild index;
- open quarantine;
- open conflicts.

The plugin must call the local service and must not contain unrestricted autonomous logic.

## 9. Source Preservation

Every source must be preserved before processing.

Each source record must include:

- source ID;
- channel;
- sender or device;
- received timestamp;
- original text;
- original attachment;
- MIME type;
- file size;
- cryptographic hash;
- extraction status;
- extracted text;
- extraction method;
- model used;
- processing history;
- links to derived records;
- errors;
- uncertainty.

Supported inputs:

- text;
- URLs;
- photos;
- receipts;
- screenshots;
- PDFs;
- office documents;
- audio;
- voice notes;
- video;
- manually added notes;
- watched inbox folders.

## 10. Multimodal Processing

The implementation must:

- live-test each advertised Cogni-Brain capability;
- use direct model support where proven reliable;
- provide local fallbacks where required;
- preserve original media;
- preserve extracted text;
- record extraction method;
- record confidence and failure details.

Local fallbacks may use project-owned Python wrappers around local tools for:

- OCR;
- receipt extraction;
- PDF extraction;
- document extraction;
- audio transcription;
- video frame extraction.

Manual OCR or transcription must not be required during normal use.

## 11. Autonomous Agent Loop

Implement a bounded and durable Python agent loop.

Required lifecycle:

1. preserve source;
2. create a visible task record;
3. gather bounded context;
4. call Cogni-Brain;
5. parse exactly one typed tool request or final proposal;
6. validate the request;
7. execute one bounded tool;
8. persist the observation;
9. continue until:
   - completed;
   - needs clarification;
   - quarantined;
   - failed after retry limit.

Required controls:

- maximum steps;
- maximum retries;
- repeated-tool detection;
- maximum context budget;
- maximum observation size;
- model timeout;
- tool timeout;
- stop-condition verification;
- loop detection;
- idempotency;
- crash recovery.

## 12. Autonomy Model

### Level 1 — Observe automatically

Allowed without confirmation:

- preserve source;
- hash;
- transcribe;
- OCR;
- extract metadata;
- classify;
- index;
- create provenance links.

### Level 2 — Organise automatically

Allowed without confirmation when policy and confidence thresholds are met:

- create or update entities;
- add aliases;
- create wiki links;
- create backlinks;
- update low-risk summaries;
- consolidate duplicate sources;
- maintain dashboards.

### Level 3 — Act with bounded authority

Allowed only under explicit user-defined policies:

- create reminders;
- create internal tasks;
- schedule internal reviews;
- draft messages;
- prepare plans;
- mark stale items;
- update internal status.

### Level 4 — Always require confirmation

- external communication;
- financial actions;
- purchases;
- deletion;
- irreversible changes;
- legal decisions;
- medical decisions;
- sensitive family conclusions;
- sensitive work conclusions;
- any materially consequential action.

Required controls:

- global pause or kill switch;
- per-domain autonomy settings;
- quiet hours;
- notification thresholds;
- rate limits;
- resource limits.

## 13. Required Typed Tools

Implement project-owned typed tools for:

- source capture;
- attachment inspection;
- image extraction;
- receipt extraction;
- PDF extraction;
- document extraction;
- audio transcription;
- video inspection;
- vault search;
- entity search;
- concept search;
- note read;
- backlink read;
- policy read;
- clarification request;
- proposal submission;
- proposal validation;
- write-plan creation;
- controlled write application;
- write verification;
- conflict creation;
- quarantine;
- retry;
- task status;
- index rebuild;
- integrity check;
- daily review;
- weekly review;
- slow-burn synthesis;
- vault question answering.

Every tool must define:

- strict input schema;
- strict output schema;
- timeout;
- size limits;
- allowed paths;
- error codes;
- audit events;
- tests.

## 14. Firehose Processing

The system must process high-volume input without creating another manual-review queue.

Required capabilities:

- exact deduplication;
- semantic deduplication;
- alias resolution;
- cautious entity merging;
- contradiction detection;
- confidence tracking;
- source weighting;
- low-value noise suppression;
- source retention;
- stale-action detection;
- relevance decay;
- periodic consolidation;
- evergreen promotion;
- unresolved-item tracking;
- archive rules;
- prioritisation;
- backpressure;
- batch processing for low-priority inputs.

Required measurable controls:

- configurable backlog limit;
- amber and red backlog thresholds;
- configurable processing priorities;
- index-freshness target;
- context budget per task;
- processing-time budget per task;
- bounded retries;
- graceful degradation when Cogni-Brain is slow or unavailable.

## 15. Knowledge Model

The vault must visibly distinguish:

- raw source;
- extracted fact;
- user-authored statement;
- model inference;
- tentative interpretation;
- disputed claim;
- contradiction;
- verified conclusion;
- action;
- duty;
- commitment;
- decision;
- event;
- entity;
- concept;
- relationship;
- evergreen synthesis;
- output draft.

Use consistent Markdown frontmatter and wiki links.

## 16. Retrieval at Scale

The system must support citation-backed retrieval across:

- 10,000 notes;
- 50,000 notes;
- 100,000 notes.

Required retrieval layers:

- title and alias lookup;
- frontmatter and tag lookup;
- full-text index;
- entity index;
- concept index;
- wiki-link and backlink graph;
- date filters;
- source-type filters;
- optional local semantic embeddings;
- bounded re-ranking;
- bounded context assembly.

Required evidence:

- no full-vault scan for normal queries;
- incremental index updates;
- full rebuild command;
- retrieval-health report;
- latency measurements;
- precision and recall evaluation;
- exact source citations.

## 17. Slow-Burn Outputs

The system must identify themes accumulating across weeks, months, and years.

Supported outputs:

- essays;
- personal principles;
- family insights;
- professional lessons;
- research themes;
- product ideas;
- operating procedures;
- decision frameworks;
- learning guides;
- comparisons between ancient and modern knowledge.

Every output must link to supporting sources, claims, entities, concepts, and prior insights.

## 18. Minimal Dashboard

Use green, amber, and red indicators for:

- ingestion health;
- backlog;
- failed or quarantined tasks;
- conflicts;
- overdue commitments;
- work risks;
- family and relationship concerns;
- financial and administrative issues;
- stale projects;
- neglected life areas;
- knowledge quality;
- retrieval health;
- model and tool health;
- slow-burn outputs gaining evidence.

Every indicator must be explainable and link to supporting records.

## 19. Cogni-Brain / Qwen Failure Modes

The system must explicitly test and defend against:

- `content: null`;
- reasoning present without a final answer;
- differences between `content`, `reasoning`, and `reasoning_content`;
- malformed JSON;
- nested JSON;
- malformed tool calls;
- truncated output;
- repeated tool calls;
- endless loops;
- premature completion;
- incorrect stopping;
- semantically wrong but schema-valid output;
- unsupported authorship;
- fabricated evidence;
- exact-language loss;
- incorrect entity merges;
- wrong personal or work routing;
- confidentiality leakage;
- prompt injection in text, images, PDFs, audio, or video;
- oversized context;
- oversized observations;
- endpoint timeout;
- endpoint error;
- restart during model call;
- restart during tool execution;
- restart during write;
- duplicate delivery;
- out-of-order delivery;
- nondeterministic repeated runs.

## 20. Automated Evaluation Framework

The project must include an automated evaluation harness that the implementing LLM can execute repeatedly.

### 20.1 Evaluation categories

- installation;
- configuration;
- model contract;
- parser;
- tool schemas;
- state machine;
- security;
- path safety;
- iCloud file stability;
- conflict handling;
- atomic writes;
- ingestion;
- OCR;
- document extraction;
- transcription;
- video;
- retrieval;
- 10k, 50k, and 100k scale;
- entity resolution;
- concept linking;
- deduplication;
- contradiction detection;
- confidentiality;
- prompt injection;
- live Cogni-Brain;
- repeated Cogni-Brain runs;
- multi-step loops;
- long context;
- restart and recovery;
- concurrency;
- PWA;
- backup and restore;
- end-to-end vault state;
- soak;
- failure injection.

### 20.2 Evaluation record

Every evaluation must record:

- evaluation ID;
- requirement ID;
- test name;
- severity;
- test data;
- expected result;
- actual result;
- pass or fail;
- logs;
- evidence path;
- timestamp;
- model version;
- code version;
- environment details.

### 20.3 Iterative improvement loop

The implementing LLM must:

1. run the full evaluation suite;
2. classify failures by severity and root cause;
3. fix one or more failures;
4. rerun affected tests;
5. rerun the full critical suite;
6. continue until production gates pass;
7. document residual risks.

The LLM must not stop after generating tests. It must execute them and iterate.

### 20.4 Production gates

Production-ready requires:

- 100% pass on critical deterministic tests;
- 100% pass on security-boundary tests;
- 100% pass on write-integrity tests;
- 100% pass on backup and restore tests;
- 100% pass on restart-recovery tests;
- 100% pass on privacy and confidentiality tests;
- repeated live Cogni-Brain success above a documented and justified threshold;
- zero unhandled crashes during soak testing;
- retrieval quality and latency within documented thresholds;
- proven iCloud conflict handling;
- proven unattended ingestion;
- no unresolved critical or high-severity defect.

### 20.5 Live-model thresholds

Define and justify thresholds for:

- tool-call validity;
- proposal validity;
- repeated-run consistency;
- evidence grounding;
- hallucination rate;
- routing accuracy;
- entity-resolution accuracy;
- clarification accuracy;
- safe-quarantine accuracy.

A single successful run is insufficient.

## 21. Realistic Scenario Matrix

Tests must cover:

- family;
- work;
- school;
- health administration;
- bills;
- receipts;
- travel;
- home maintenance;
- insurance;
- subscriptions;
- relationships;
- learning;
- books;
- research;
- spiritual material;
- ancient texts;
- modern knowledge;
- decisions;
- commitments;
- long-term goals;
- creative projects;
- emotionally charged input;
- incomplete messages;
- ambiguous references;
- duplicates;
- contradictions;
- confidential work;
- mixed personal and work input;
- adversarial prompt injection;
- hidden instructions inside media.

## 22. Backup and Recovery

Required:

- one-command backup;
- one-command restore;
- versioned backups;
- backup integrity verification;
- restore rehearsal;
- missing-attachment detection;
- broken-link detection;
- corrupt-note detection;
- index rebuild after restore;
- documented recovery point objective;
- documented recovery time objective.

## 23. Documentation

Documentation must match the actual implementation.

Required documents:

- architecture;
- vault model;
- source-of-truth rules;
- environment separation;
- installation;
- configuration;
- startup and shutdown;
- PWA use;
- iPhone use;
- Obsidian use;
- supported inputs;
- model contract;
- tool contracts;
- security model;
- privacy boundaries;
- autonomy model;
- task lifecycle;
- backup and restore;
- upgrades;
- diagnostics;
- quarantine;
- retries;
- testing;
- evaluation framework;
- performance;
- Qwen limitations;
- residual risks;
- troubleshooting.

## 24. Final Deliverables

Deliver:

- complete source code;
- clean development vault;
- disposable iCloud integration-test vault setup;
- production-vault activation procedure;
- Python service;
- private PWA;
- optional Obsidian plugin;
- typed tools;
- multimodal ingestion;
- retrieval and index layer;
- deterministic validators;
- safe write engine;
- iCloud conflict handling;
- autonomy controls;
- quarantine and audit system;
- dashboard;
- backup and restore;
- automated evaluation harness;
- raw evaluation evidence;
- risk and coverage matrix;
- one-command installer;
- one-command start;
- one-command test runner;
- one-command evaluation runner;
- one-command index rebuild;
- one-command integrity check;
- operating documentation;
- production-readiness report;
- explicit residual risks.
