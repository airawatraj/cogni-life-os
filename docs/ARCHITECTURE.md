# Architecture

Cogni Life OS is local-first:

```text
Private PWA -> local Python service -> typed tools -> Obsidian Markdown vault
                                             |
                                             v
                                     Cogni-Brain endpoint
```

The Markdown vault is authoritative. SQLite indexes and runtime files under `.cogni/runtime` are disposable and rebuildable.

This implementation creates only the local development vault at `vaults/dev-vault`. iCloud integration and production activation are documented gates, not active targets for this session.
