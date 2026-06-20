from __future__ import annotations

import json
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .auth import TokenStore
from .config import Settings
from .evaluation import run as run_eval
from .indexer import Index
from .ingest import capture_text
from .ingest import capture_binary
from .integrity import scan
from .markdown import parse_frontmatter
from .model_contract import discover_endpoint
from .vault import Vault


APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#f6f7f2" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#101615" media="(prefers-color-scheme: dark)">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Cogni Life OS">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <title>Cogni Life OS</title>
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/icon.svg" type="image/svg+xml">
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f2;
      --panel: #ffffff;
      --panel-2: #eef4f1;
      --text: #17201f;
      --muted: #63706d;
      --line: #dce3de;
      --brand: #0b6f68;
      --brand-2: #1e8f83;
      --accent: #295b8d;
      --ok: #d9efe3;
      --warn: #fff1c7;
      --bad: #ffe0dd;
      --shadow: 0 18px 45px rgba(21, 34, 31, .10);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #101615;
        --panel: #18211f;
        --panel-2: #202d2a;
        --text: #eff5f1;
        --muted: #aab8b2;
        --line: #2d3c38;
        --brand: #46c6b4;
        --brand-2: #75dccd;
        --accent: #9fc7f2;
        --ok: #17382d;
        --warn: #443716;
        --bad: #45231f;
        --shadow: 0 18px 45px rgba(0, 0, 0, .28);
      }
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--brand) 14%, transparent), transparent 30rem),
        var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }
    button, input, textarea { font: inherit; }
    button { min-height: 44px; touch-action: manipulation; }
    .app {
      min-height: 100dvh;
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
    }
    .rail {
      border-right: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 88%, transparent);
      padding: calc(18px + env(safe-area-inset-top)) 18px calc(18px + env(safe-area-inset-bottom));
      display: flex;
      flex-direction: column;
      gap: 18px;
      position: sticky;
      top: 0;
      height: 100dvh;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .mark {
      width: 42px; height: 42px; border-radius: 8px;
      display: grid; place-items: center;
      color: white; font-weight: 800;
      background: linear-gradient(135deg, #0b6f68, #7d4f95);
      box-shadow: var(--shadow);
    }
    .brand h1 { font-size: 18px; line-height: 1.1; margin: 0; letter-spacing: 0; }
    .brand p { margin: 3px 0 0; color: var(--muted); font-size: 13px; }
    .status-stack { display: grid; gap: 8px; }
    .pill {
      display: inline-flex; align-items: center; gap: 8px;
      min-height: 32px; border: 1px solid var(--line);
      border-radius: 999px; padding: 6px 10px;
      color: var(--muted); background: var(--panel);
      font-size: 13px;
    }
    .dot { width: 8px; height: 8px; border-radius: 99px; background: var(--brand-2); flex: 0 0 auto; }
    .dot.warn { background: #d59f1a; }
    .dot.bad { background: #db5b51; }
    .nav { display: grid; gap: 6px; margin-top: 4px; }
    .nav a {
      color: var(--muted); text-decoration: none; min-height: 44px;
      display: flex; align-items: center; gap: 10px;
      padding: 10px 12px; border-radius: 8px;
    }
    .nav a.active { color: var(--text); background: var(--panel-2); font-weight: 700; }
    .launch {
      margin-top: auto; display: grid; gap: 12px;
      padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
    }
    .qr {
      width: 148px; height: 148px; border-radius: 8px;
      background: white; padding: 8px; display: grid; place-items: center;
      border: 1px solid var(--line);
    }
    .qr img { width: 132px; height: 132px; image-rendering: pixelated; }
    .warning { background: var(--warn); border: 1px solid color-mix(in srgb, #d59f1a 35%, var(--line)); color: var(--text); padding: 10px; border-radius: 8px; font-size: 13px; }
    .main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      height: 100dvh;
    }
    .topbar {
      display: none;
      padding: calc(12px + env(safe-area-inset-top)) 14px 10px;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 94%, transparent);
      align-items: center; justify-content: space-between; gap: 10px;
    }
    .view { min-height: 0; overflow: auto; padding: 22px; }
    .screen { display: none; max-width: 1120px; margin: 0 auto; }
    .screen.active { display: block; }
    .chat-shell {
      max-width: 980px; height: calc(100dvh - 44px);
      margin: 0 auto; display: grid; grid-template-rows: auto minmax(0, 1fr) auto;
      border: 1px solid var(--line); border-radius: 8px; background: color-mix(in srgb, var(--panel) 94%, transparent);
      box-shadow: var(--shadow); overflow: hidden;
    }
    .chat-head {
      padding: 14px 16px; border-bottom: 1px solid var(--line);
      display: flex; justify-content: space-between; gap: 10px; align-items: center;
    }
    .messages { min-height: 0; overflow: auto; padding: 18px; display: flex; flex-direction: column; gap: 14px; }
    .msg { display: flex; flex-direction: column; gap: 8px; max-width: min(760px, 88%); }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .bubble {
      padding: 12px 14px; border-radius: 8px;
      background: var(--panel-2); color: var(--text); line-height: 1.45;
      border: 1px solid transparent;
    }
    .user .bubble { background: color-mix(in srgb, var(--accent) 15%, var(--panel)); color: var(--text); }
    .meta { color: var(--muted); font-size: 12px; }
    .sources, .proposal, .error-card {
      display: grid; gap: 8px; padding: 10px; border-radius: 8px;
      border: 1px solid var(--line); background: var(--panel);
    }
    .source-link { color: var(--accent); text-decoration: none; font-size: 13px; overflow-wrap: anywhere; }
    .proposal { border-color: color-mix(in srgb, var(--brand) 40%, var(--line)); }
    .error-card { background: var(--bad); border-color: color-mix(in srgb, #db5b51 36%, var(--line)); }
    .composer {
      border-top: 1px solid var(--line); padding: 12px max(12px, env(safe-area-inset-right)) calc(12px + env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
      display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 8px; align-items: end;
      background: var(--panel);
    }
    .icon-btn, .send {
      border: 1px solid var(--line); background: var(--panel-2); color: var(--text);
      border-radius: 8px; width: 46px; height: 46px; display: grid; place-items: center; cursor: pointer;
    }
    .icon-btn[disabled] { opacity: .45; cursor: not-allowed; }
    .send { background: var(--brand); color: white; border-color: var(--brand); }
    textarea, input {
      width: 100%; border: 1px solid var(--line); border-radius: 8px;
      background: var(--panel); color: var(--text); padding: 12px 13px;
      outline-color: var(--brand);
    }
    textarea { resize: vertical; min-height: 46px; max-height: 180px; }
    .panel-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .panel {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
      padding: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.04);
    }
    .panel h2 { margin: 0 0 10px; font-size: 20px; letter-spacing: 0; }
    .panel h3 { margin: 0 0 8px; font-size: 15px; }
    .stack { display: grid; gap: 12px; }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .button {
      border: 0; border-radius: 8px; padding: 10px 14px;
      background: var(--brand); color: white; cursor: pointer; font-weight: 700;
    }
    .button.secondary { background: var(--panel-2); color: var(--text); border: 1px solid var(--line); }
    .list { display: grid; gap: 10px; }
    .item { padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
    .muted { color: var(--muted); }
    .small { font-size: 13px; }
    .login {
      position: fixed; inset: 0; z-index: 5; display: grid; place-items: center;
      padding: 18px; background: color-mix(in srgb, var(--bg) 88%, black 12%);
    }
    .login.hidden { display: none; }
    .login-card {
      width: min(440px, 100%); background: var(--panel); border: 1px solid var(--line);
      border-radius: 8px; padding: 22px; box-shadow: var(--shadow); display: grid; gap: 14px;
    }
    details { border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: var(--panel); }
    pre { white-space: pre-wrap; overflow: auto; max-height: 360px; font-size: 12px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    @media (max-width: 860px) {
      .app { display: block; }
      .rail { display: none; }
      .topbar { display: flex; position: sticky; top: 0; z-index: 2; }
      .main { display: block; height: auto; min-height: 100dvh; }
      .view { padding: 0; min-height: calc(100dvh - 69px); }
      .screen { max-width: none; }
      .screen:not(#chat) { padding: 16px 14px calc(86px + env(safe-area-inset-bottom)); }
      .chat-shell { height: calc(100dvh - 137px - env(safe-area-inset-bottom)); border: 0; border-radius: 0; box-shadow: none; }
      .chat-head { padding: 12px 14px; }
      .messages { padding: 14px; }
      .msg { max-width: 92%; }
      .panel-grid { grid-template-columns: 1fr; }
      .mobile-nav {
        position: fixed; left: 0; right: 0; bottom: 0; z-index: 3;
        display: grid; grid-template-columns: repeat(5, 1fr);
        padding: 6px max(8px, env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left));
        border-top: 1px solid var(--line); background: var(--panel);
      }
      .mobile-nav a { min-height: 48px; display: grid; place-items: center; color: var(--muted); text-decoration: none; font-size: 12px; border-radius: 8px; }
      .mobile-nav a.active { background: var(--panel-2); color: var(--text); font-weight: 700; }
    }
    @media (min-width: 861px) { .mobile-nav { display: none; } }
  </style>
</head>
<body>
<div class="app">
  <aside class="rail">
    <div class="brand">
      <div class="mark" aria-hidden="true">CL</div>
      <div><h1>Cogni Life OS</h1><p>Local household intelligence</p></div>
    </div>
    <div class="status-stack" aria-label="Service status">
      <div class="pill"><span id="serviceDot" class="dot warn"></span><span id="serviceStatus">Locked</span></div>
      <div class="pill"><span class="dot warn" id="modelDot"></span><span id="modelStatus">Model unknown</span></div>
      <div class="pill"><span class="dot warn" id="vaultDot"></span><span id="vaultStatus">Vault unknown</span></div>
      <div class="pill"><span class="dot warn" id="indexDot"></span><span id="indexStatus">Index unknown</span></div>
      <div class="pill"><span class="dot" id="safeDot"></span><span id="safeStatus">Safe operations on</span></div>
    </div>
    <nav class="nav" aria-label="Main navigation">
      <a href="#chat" data-route="chat">Chat</a>
      <a href="#capture" data-route="capture">Capture</a>
      <a href="#knowledge" data-route="knowledge">Knowledge</a>
      <a href="#tasks" data-route="tasks">Tasks</a>
      <a href="#settings" data-route="settings">Settings</a>
    </nav>
    <section class="launch" aria-label="Desktop launch screen">
      <div class="row"><strong>Launch</strong><span class="pill"><span class="dot warn" id="launchDot"></span><span id="launchStatus">Checking</span></span></div>
      <div class="small muted" id="localUrl">Local URL unavailable</div>
      <div class="qr"><img id="qrImage" alt="QR code for current PWA URL"></div>
      <div class="small muted" id="modelEndpoint">Model endpoint unavailable</div>
      <div class="warning" id="phoneWarning" hidden>Phone access unavailable: service is bound to 127.0.0.1</div>
    </section>
  </aside>

  <main class="main">
    <header class="topbar">
      <div class="brand"><div class="mark" aria-hidden="true">CL</div><div><h1>Cogni Life OS</h1><p id="mobileSub">Locked</p></div></div>
      <button class="icon-btn" id="refreshBtn" title="Refresh status" aria-label="Refresh status">R</button>
    </header>
    <div class="view">
      <section id="chat" class="screen active" data-title="Chat">
        <div class="chat-shell">
          <div class="chat-head">
            <div>
              <strong>Cogni</strong>
              <div class="small muted">Search-backed conversation with your local vault</div>
            </div>
            <div class="pill"><span class="dot warn" id="chatModelDot"></span><span id="activeModel">Model unavailable</span></div>
          </div>
          <div class="messages" id="messages" aria-live="polite"></div>
          <form class="composer" id="chatForm">
            <label class="icon-btn" title="Attach image or document" aria-label="Attach image or document">
              +<input class="sr-only" id="chatFile" type="file" accept="image/*,.pdf,.txt,.md,.docx">
            </label>
            <button class="icon-btn" id="voiceBtn" type="button" disabled title="Voice notes unavailable in this browser/service">Mic</button>
            <textarea id="chatInput" rows="1" placeholder="Ask Cogni..." autocomplete="off"></textarea>
            <button class="send" type="submit" title="Send" aria-label="Send">Send</button>
          </form>
        </div>
      </section>

      <section id="capture" class="screen" data-title="Capture">
        <div class="panel-grid">
          <div class="panel stack">
            <h2>Capture</h2>
            <textarea id="captureText" rows="7" placeholder="Capture a note, decision, commitment, link, or household detail"></textarea>
            <button class="button" id="captureBtn">Save note</button>
            <div class="item small muted" id="captureResult">Ready to capture into the local vault.</div>
          </div>
          <div class="panel stack">
            <h2>Upload</h2>
            <input id="uploadInput" type="file" accept="image/*,.pdf,.txt,.md,.docx">
            <button class="button" id="uploadBtn">Upload source</button>
            <div class="item small muted" id="uploadResult">Images and documents are preserved as sources when extraction is supported.</div>
          </div>
        </div>
      </section>

      <section id="knowledge" class="screen" data-title="Knowledge">
        <div class="panel stack">
          <h2>Knowledge</h2>
          <div class="row"><input id="knowledgeQuery" placeholder="Search the vault"><button class="button" id="knowledgeSearchBtn">Search</button></div>
          <div class="list" id="knowledgeResults"></div>
        </div>
      </section>

      <section id="tasks" class="screen" data-title="Tasks">
        <div class="panel stack">
          <div class="row"><h2>Tasks</h2><button class="button secondary" id="taskRefreshBtn">Refresh</button></div>
          <div class="list" id="taskList"></div>
        </div>
      </section>

      <section id="settings" class="screen" data-title="Settings">
        <div class="panel-grid">
          <div class="panel stack">
            <h2>Settings</h2>
            <div class="item"><strong>Theme</strong><div class="small muted">Follows the system light or dark setting.</div></div>
            <div class="item"><strong>Remote access</strong><div class="small muted" id="remoteState">Loopback-only by default.</div></div>
            <div class="item"><strong>Voice notes</strong><div class="small muted">Disabled until browser recording and backend ingestion are available together.</div></div>
            <button class="button secondary" id="logoutBtn">Forget service token</button>
          </div>
          <div class="panel stack">
            <h2>Status</h2>
            <div id="settingsStatus" class="list"></div>
            <button class="button secondary" id="advancedBtn">Advanced diagnostics</button>
          </div>
        </div>
      </section>

      <section id="advanced" class="screen" data-title="Advanced">
        <div class="panel stack">
          <div class="row"><h2>Advanced</h2><button class="button secondary" id="backSettingsBtn">Settings</button></div>
          <div class="panel-grid">
            <div class="panel stack"><h3>Integrity</h3><button class="button secondary" id="integrityBtn">Run integrity</button><div id="integrityOut" class="small muted"></div></div>
            <div class="panel stack"><h3>Evaluation</h3><button class="button secondary" id="evaluateBtn">Run evaluation</button><div id="evaluateOut" class="small muted"></div></div>
            <div class="panel stack"><h3>Indexing</h3><div id="indexAdmin" class="small muted">Index rebuild runs after capture and upload.</div></div>
            <div class="panel stack"><h3>Backup</h3><div class="small muted">Use the local backup script or CLI for now.</div></div>
            <div class="panel stack"><h3>Operations</h3><div class="small muted">Safe-operation controls remain bounded by local policy.</div></div>
            <div class="panel stack"><h3>Model diagnostics</h3><button class="button secondary" id="modelCheckBtn">Check endpoint</button><div id="modelDiagOut" class="small muted"></div></div>
          </div>
          <details><summary>Raw diagnostics</summary><pre id="rawDiagnostics"></pre></details>
        </div>
      </section>
    </div>
  </main>

  <nav class="mobile-nav" aria-label="Mobile navigation">
    <a href="#chat" data-route="chat">Chat</a>
    <a href="#capture" data-route="capture">Capture</a>
    <a href="#knowledge" data-route="knowledge">Knowledge</a>
    <a href="#tasks" data-route="tasks">Tasks</a>
    <a href="#settings" data-route="settings">Settings</a>
  </nav>
</div>

<div class="login" id="login">
  <form class="login-card" id="loginForm">
    <div class="brand"><div class="mark" aria-hidden="true">CL</div><div><h1>Cogni Life OS</h1><p>Authenticate to your local service</p></div></div>
    <label class="stack">Service token<input id="tokenInput" type="password" autocomplete="current-password" placeholder="Paste your service token"></label>
    <button class="button" type="submit">Unlock</button>
    <div class="small muted" id="loginError">The token stays in this browser and is sent only to this local service.</div>
  </form>
</div>

<template id="proposalTemplate">
  <div class="proposal">
    <strong>Proposed action</strong>
    <div class="small muted">Capture this message as a source in the vault?</div>
    <div class="row"><button class="button approve" type="button">Approve</button><button class="button secondary reject" type="button">Reject</button></div>
  </div>
</template>

<script>
const state = {
  token: localStorage.getItem("cogni_token") || "",
  status: null,
  messages: [],
  pendingProposal: null
};
const $ = (id) => document.getElementById(id);
const views = ["chat", "capture", "knowledge", "tasks", "settings", "advanced"];
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => {
    if (ch === "&") return "&amp;";
    if (ch === "<") return "&lt;";
    if (ch === ">") return "&gt;";
    if (ch === '"') return "&quot;";
    return "&#39;";
  });
}
async function api(path, options={}) {
  const headers = Object.assign({"Authorization": "Bearer " + state.token}, options.headers || {});
  const response = await fetch(path, Object.assign({}, options, {headers}));
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = {error: "invalid_json", detail: text}; }
  if (!response.ok) {
    const err = new Error(data.detail || data.error || "Request failed");
    err.data = data;
    err.status = response.status;
    throw err;
  }
  return data;
}
function route() {
  const name = (location.hash || "#chat").slice(1);
  const active = views.includes(name) ? name : "chat";
  document.querySelectorAll(".screen").forEach(el => el.classList.toggle("active", el.id === active));
  document.querySelectorAll("[data-route]").forEach(el => el.classList.toggle("active", el.dataset.route === active));
  if (active === "tasks") loadTasks();
  if (active === "settings") renderSettings();
}
function setDot(id, status) {
  const el = $(id);
  if (!el) return;
  el.className = "dot" + (status === "bad" ? " bad" : status === "warn" ? " warn" : "");
}
function renderStatus(status) {
  state.status = status;
  $("serviceStatus").textContent = status.service.status === "online" ? "Service online" : "Service unavailable";
  $("mobileSub").textContent = status.service.status === "online" ? "Local service online" : "Service unavailable";
  $("modelStatus").textContent = status.model.name;
  $("activeModel").textContent = status.model.name;
  $("vaultStatus").textContent = status.vault.status === "ready" ? "Vault ready" : "Vault unavailable";
  $("indexStatus").textContent = `${status.index.note_count || 0} indexed notes`;
  $("safeStatus").textContent = status.safe_operations.status;
  $("launchStatus").textContent = status.service.status;
  $("localUrl").textContent = status.service.local_url;
  $("modelEndpoint").textContent = `${status.model.endpoint} . ${status.model.endpoint_status}`;
  $("remoteState").textContent = status.service.loopback_only ? "Loopback-only: phones cannot reach this service." : "Reachable URL is configured for this session.";
  $("phoneWarning").hidden = !status.service.loopback_only;
  setDot("serviceDot", "ok"); setDot("vaultDot", status.vault.status === "ready" ? "ok" : "bad");
  setDot("indexDot", "ok"); setDot("safeDot", "ok"); setDot("launchDot", status.service.loopback_only ? "warn" : "ok");
  setDot("modelDot", status.model.endpoint_status === "online" ? "ok" : "warn");
  setDot("chatModelDot", status.model.endpoint_status === "online" ? "ok" : "warn");
  renderSettings();
  $("qrImage").src = "/qr.svg?url=" + encodeURIComponent(status.service.reachable_url || status.service.local_url);
}
async function refreshStatus() {
  const status = await api("/api/app-status");
  renderStatus(status);
  $("rawDiagnostics").textContent = JSON.stringify(status, null, 2);
}
function addMessage(role, htmlContent, extra="") {
  const item = {role, htmlContent, extra, ts: new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})};
  state.messages.push(item);
  renderMessages();
}
function renderMessages() {
  $("messages").innerHTML = state.messages.map(m => `
    <article class="msg ${m.role}">
      <div class="bubble">${m.htmlContent}</div>
      ${m.extra || ""}
      <div class="meta">${m.role === "user" ? "You" : "Cogni"} . ${m.ts}</div>
    </article>
  `).join("");
  $("messages").scrollTop = $("messages").scrollHeight;
}
function sourcesHtml(results) {
  if (!results || !results.length) return "";
  return `<div class="sources"><strong>Sources</strong>${results.map((r, i) => `<a class="source-link" href="#knowledge" data-q="${escapeHtml(r.title || r.path)}">[${i + 1}] ${escapeHtml(r.title || r.path)} . ${escapeHtml(r.path)}</a>`).join("")}</div>`;
}
function proposalHtml(text) {
  const id = "proposal-" + Date.now();
  queueMicrotask(() => {
    const card = document.querySelector(`[data-proposal="${id}"]`);
    if (!card) return;
    card.querySelector(".approve").addEventListener("click", async () => {
      await captureNote(text, "chat");
      card.innerHTML = "<strong>Approved</strong><div class='small muted'>Captured into the vault.</div>";
    });
    card.querySelector(".reject").addEventListener("click", () => {
      card.innerHTML = "<strong>Rejected</strong><div class='small muted'>No vault write was made.</div>";
    });
  });
  return `<div class="proposal" data-proposal="${id}"><strong>Proposed action</strong><div class="small muted">Capture this as a source in the vault?</div><div class="row"><button class="button approve" type="button">Approve</button><button class="button secondary reject" type="button">Reject</button></div></div>`;
}
async function sendChat(text) {
  addMessage("user", escapeHtml(text));
  const results = await searchVault(text);
  if (results.length) {
    const lead = `I found ${results.length} relevant source${results.length === 1 ? "" : "s"} in your vault. Open the citations below to inspect the underlying notes.`;
    addMessage("assistant", escapeHtml(lead), sourcesHtml(results));
  } else {
    const disabled = state.status?.model?.endpoint_status === "online" ? "No matching vault sources were found for this question." : "No matching vault sources were found. Live model answering is not exposed by this service yet, so I will not invent an answer.";
    addMessage("assistant", escapeHtml(disabled), proposalHtml(text));
  }
}
async function searchVault(query) {
  const data = await api("/api/search?q=" + encodeURIComponent(query || "source"));
  return data.results || [];
}
async function captureNote(text, channel="pwa") {
  return await api("/api/capture-text", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text, channel, sender:"user"})});
}
async function uploadFile(file) {
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
  const data_base64 = String(dataUrl).split(",", 2)[1] || "";
  return await api("/api/upload", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({filename:file.name, data_base64, channel:"pwa", sender:"user"})});
}
function renderSearchResults(target, results) {
  $(target).innerHTML = results.length ? results.map((r, i) => `
    <div class="item">
      <strong>${escapeHtml(r.title || r.path)}</strong>
      <div class="small muted">${escapeHtml(r.path)} . score ${escapeHtml(r.score ?? "n/a")}</div>
      <div class="small muted">Citation [${i + 1}] . ${escapeHtml((r.reasons || []).join(", ") || "full-text match")}</div>
    </div>`).join("") : `<div class="item muted">No sources found.</div>`;
}
async function loadTasks() {
  try {
    const data = await api("/api/tasks");
    $("taskList").innerHTML = data.tasks.length ? data.tasks.map(t => `
      <div class="item"><strong>${escapeHtml(t.title)}</strong><div class="small muted">${escapeHtml(t.status)} . ${escapeHtml(t.path)}</div></div>
    `).join("") : `<div class="item muted">No task records yet.</div>`;
  } catch (err) { showError("taskList", err); }
}
function renderSettings() {
  if (!state.status) return;
  $("settingsStatus").innerHTML = [
    ["Service", state.status.service.status],
    ["Local URL", state.status.service.local_url],
    ["Model", state.status.model.name],
    ["Vault", state.status.vault.path],
    ["Index", `${state.status.index.note_count || 0} notes`],
    ["Safe operations", state.status.safe_operations.status]
  ].map(([k,v]) => `<div class="item"><strong>${escapeHtml(k)}</strong><div class="small muted">${escapeHtml(v)}</div></div>`).join("");
}
function showError(target, err) {
  $(target).innerHTML = `<div class="error-card"><strong>Error</strong><div class="small">${escapeHtml(err.message || err)}</div></div>`;
}
async function bootstrap() {
  $("tokenInput").value = state.token;
  if (state.token) {
    try {
      await refreshStatus();
      $("login").classList.add("hidden");
      addMessage("assistant", "Welcome back. I can search your vault, capture memories, preserve uploads, and show citations. Live voice and unrestricted model actions stay disabled until the local service exposes them.");
    } catch { $("login").classList.remove("hidden"); }
  }
}
$("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.token = $("tokenInput").value.trim();
  try {
    await refreshStatus();
    localStorage.setItem("cogni_token", state.token);
    $("login").classList.add("hidden");
    addMessage("assistant", "Service unlocked. Model, vault, indexing, and safe-operation status are visible in the sidebar.");
  } catch (err) {
    $("loginError").textContent = err.status === 401 ? "Authentication failed. Check the service token." : err.message;
  }
});
$("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("chatInput").value.trim();
  if (!text) return;
  $("chatInput").value = "";
  try { await sendChat(text); } catch (err) { addMessage("assistant", "Something went wrong.", `<div class="error-card">${escapeHtml(err.message)}</div>`); }
});
$("chatFile").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  addMessage("user", `Attached ${escapeHtml(file.name)}`);
  try {
    const result = await uploadFile(file);
    addMessage("assistant", `Preserved ${escapeHtml(file.name)} as a vault source.`, sourcesHtml([{title: result.source_id, path: result.source_path, score: 1, reasons:["uploaded_source"]}]));
    await refreshStatus();
  } catch (err) { addMessage("assistant", "Upload failed.", `<div class="error-card">${escapeHtml(err.message)}</div>`); }
});
$("captureBtn").addEventListener("click", async () => {
  const text = $("captureText").value.trim();
  if (!text) return;
  try {
    const r = await captureNote(text, "pwa");
    $("captureResult").textContent = `${r.duplicate ? "Already captured" : "Captured"} . ${r.source_id}`;
    $("captureText").value = "";
    await refreshStatus();
  } catch (err) { $("captureResult").textContent = err.message; }
});
$("uploadBtn").addEventListener("click", async () => {
  const file = $("uploadInput").files[0];
  if (!file) return;
  try {
    const r = await uploadFile(file);
    $("uploadResult").textContent = `Uploaded . ${r.source_id} . ${r.extraction.status}`;
    await refreshStatus();
  } catch (err) { $("uploadResult").textContent = err.message; }
});
$("knowledgeSearchBtn").addEventListener("click", async () => {
  try { renderSearchResults("knowledgeResults", await searchVault($("knowledgeQuery").value)); } catch (err) { showError("knowledgeResults", err); }
});
$("taskRefreshBtn").addEventListener("click", loadTasks);
$("refreshBtn").addEventListener("click", refreshStatus);
$("logoutBtn").addEventListener("click", () => { localStorage.removeItem("cogni_token"); location.reload(); });
$("advancedBtn").addEventListener("click", () => { location.hash = "#advanced"; });
$("backSettingsBtn").addEventListener("click", () => { location.hash = "#settings"; });
$("integrityBtn").addEventListener("click", async () => { const r = await api("/api/integrity"); $("integrityOut").textContent = r.status; $("rawDiagnostics").textContent = JSON.stringify(r, null, 2); });
$("evaluateBtn").addEventListener("click", async () => { const r = await api("/api/evaluate", {method:"POST"}); $("evaluateOut").textContent = r.status || "Evaluation complete"; $("rawDiagnostics").textContent = JSON.stringify(r, null, 2); });
$("modelCheckBtn").addEventListener("click", async () => { const r = await api("/api/model-status"); $("modelDiagOut").textContent = r.status ? "Model endpoint online" : (r.error || "Unavailable"); $("rawDiagnostics").textContent = JSON.stringify(r, null, 2); await refreshStatus(); });
window.addEventListener("hashchange", route);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
route();
bootstrap();
</script>
</body>
</html>
"""

SERVICE_WORKER = """
const CACHE = "cogni-life-os-shell-v1";
const SHELL = ["/", "/manifest.json", "/icon.svg"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then(match => match || caches.match("/"))));
});
"""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#0b6f68"/><path d="M256 88c76 38 124 96 124 164 0 82-60 142-124 172-64-30-124-90-124-172 0-68 48-126 124-164Z" fill="#f7f4ec"/><path d="M256 142c42 34 66 72 66 113 0 43-25 78-66 106-41-28-66-63-66-106 0-41 24-79 66-113Z" fill="#7d4f95"/><path d="M256 190c21 21 32 43 32 66s-11 44-32 62c-21-18-32-39-32-62s11-45 32-66Z" fill="#f0bf53"/></svg>"""


def manifest() -> dict:
    return {
        "name": "Cogni Life OS",
        "short_name": "Cogni",
        "description": "Local-first personal knowledge and household intelligence PWA.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f6f7f2",
        "theme_color": "#0b6f68",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}
        ],
    }


def app_status(settings: Settings, vault: Vault, index: Index, host_header: str | None, server_address: tuple | None = None) -> dict:
    local_url = _request_url(host_header, server_address)
    hostname = urlparse(local_url).hostname or ""
    loopback_only = hostname in {"127.0.0.1", "localhost", "::1"}
    index_health = index.health()
    return {
        "service": {
            "name": "Cogni Life OS",
            "status": "online",
            "local_url": local_url,
            "reachable_url": local_url,
            "loopback_only": loopback_only,
            "phone_warning": "Phone access unavailable: service is bound to 127.0.0.1" if loopback_only else None,
        },
        "model": {
            "name": settings.model_name,
            "endpoint": settings.model_base_url,
            "endpoint_status": "configured",
            "live_multimodal": False,
        },
        "vault": {"status": "ready" if vault.root.exists() else "missing", "path": str(vault.root)},
        "index": index_health,
        "safe_operations": {"status": "confirmation required for proposed writes", "quarantine": "enabled"},
        "features": {
            "voice_notes": False,
            "video": False,
            "remote_access": not loopback_only,
            "live_model_chat": False,
            "file_upload": True,
            "offline_shell": True,
        },
    }


def list_tasks(vault: Vault, *, limit: int = 25) -> list[dict]:
    tasks: list[dict] = []
    task_root = vault.root / "00-system" / "tasks"
    if not task_root.exists():
        return tasks
    for path in sorted(task_root.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        raw = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem)
        tasks.append({"title": title, "status": str(fm.get("status", "unknown")), "path": str(path.relative_to(vault.root)), "id": str(fm.get("id", ""))})
    return tasks


def qr_svg(value: str) -> str:
    matrix = _qr_matrix(value.encode("utf-8"))
    quiet = 4
    size = len(matrix) + quiet * 2
    cells = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                cells.append(f"M{x + quiet},{y + quiet}h1v1h-1z")
    title = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img">'
        f"<title>{title}</title><rect width=\"{size}\" height=\"{size}\" fill=\"#fff\"/>"
        f'<path fill="#111" d="{" ".join(cells)}"/></svg>'
    )


def _qr_matrix(data: bytes) -> list[list[bool]]:
    # QR version 3-L: 29x29 modules, 55 data codewords, 15 error-correction codewords.
    if len(data) > 42:
        data = data[:42]
    size = 29
    modules: list[list[bool | None]] = [[None for _ in range(size)] for _ in range(size)]
    reserved = [[False for _ in range(size)] for _ in range(size)]

    def set_module(x: int, y: int, dark: bool, reserve: bool = True) -> None:
        if 0 <= x < size and 0 <= y < size:
            modules[y][x] = dark
            if reserve:
                reserved[y][x] = True

    def finder(left: int, top: int) -> None:
        for y in range(-1, 8):
            for x in range(-1, 8):
                xx, yy = left + x, top + y
                if not (0 <= xx < size and 0 <= yy < size):
                    continue
                dark = 0 <= x <= 6 and 0 <= y <= 6 and (x in {0, 6} or y in {0, 6} or (2 <= x <= 4 and 2 <= y <= 4))
                set_module(xx, yy, dark)

    def alignment(cx: int, cy: int) -> None:
        for y in range(-2, 3):
            for x in range(-2, 3):
                set_module(cx + x, cy + y, max(abs(x), abs(y)) != 1)

    finder(0, 0)
    finder(size - 7, 0)
    finder(0, size - 7)
    alignment(22, 22)
    for i in range(8, size - 8):
        set_module(i, 6, i % 2 == 0)
        set_module(6, i, i % 2 == 0)
    set_module(8, 21, True)
    _reserve_format(modules, reserved)

    bits = _qr_data_bits(data)
    bits.extend([0] * (55 * 8 - len(bits)))
    codewords = [sum(bits[i + j] << (7 - j) for j in range(8)) for i in range(0, len(bits), 8)]
    pads = [0xEC, 0x11]
    while len(codewords) < 55:
        codewords.append(pads[len(codewords) % 2])
    codewords.extend(_reed_solomon(codewords, 15))
    stream = [(byte >> shift) & 1 for byte in codewords for shift in range(7, -1, -1)]

    bit_index = 0
    upward = True
    x = size - 1
    while x > 0:
        if x == 6:
            x -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for y in rows:
            for xx in (x, x - 1):
                if reserved[y][xx]:
                    continue
                bit = stream[bit_index] if bit_index < len(stream) else 0
                modules[y][xx] = bool(bit) ^ ((xx + y) % 2 == 0)
                bit_index += 1
        upward = not upward
        x -= 2

    _draw_format(modules, 1, 0)
    return [[bool(cell) for cell in row] for row in modules]


def _qr_data_bits(data: bytes) -> list[int]:
    bits: list[int] = []

    def append(value: int, width: int) -> None:
        bits.extend((value >> shift) & 1 for shift in range(width - 1, -1, -1))

    append(0b0100, 4)
    append(len(data), 8)
    for byte in data:
        append(byte, 8)
    terminator = min(4, 55 * 8 - len(bits))
    append(0, terminator)
    while len(bits) % 8:
        bits.append(0)
    return bits


def _reed_solomon(data: list[int], degree: int) -> list[int]:
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]

    def mul(a: int, b: int) -> int:
        return 0 if a == 0 or b == 0 else exp[log[a] + log[b]]

    generator = [1]
    for i in range(degree):
        generator = [generator[j] ^ (mul(generator[j - 1], exp[i]) if j else 0) for j in range(len(generator))] + [mul(generator[-1], exp[i])]
    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i in range(degree):
            result[i] ^= mul(generator[i + 1], factor)
    return result


def _reserve_format(modules: list[list[bool | None]], reserved: list[list[bool]]) -> None:
    size = len(modules)
    coords = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(14 - i, 8) for i in range(9, 15)]
    coords += [(size - 1 - i, 8) for i in range(8)] + [(8, size - 15 + i) for i in range(8, 15)]
    for x, y in coords:
        modules[y][x] = False
        reserved[y][x] = True


def _draw_format(modules: list[list[bool | None]], ecl: int, mask: int) -> None:
    size = len(modules)
    data = (ecl << 3) | mask
    value = data << 10
    generator = 0x537
    for i in range(14, 9, -1):
        if (value >> i) & 1:
            value ^= generator << (i - 10)
    bits = ((data << 10) | value) ^ 0x5412
    coords = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(14 - i, 8) for i in range(9, 15)]
    for i, (x, y) in enumerate(coords):
        modules[y][x] = bool((bits >> i) & 1)
    coords2 = [(size - 1 - i, 8) for i in range(8)] + [(8, size - 15 + i) for i in range(8, 15)]
    for i, (x, y) in enumerate(coords2):
        modules[y][x] = bool((bits >> i) & 1)


def _request_url(host_header: str | None, server_address: tuple | None) -> str:
    if host_header:
        return f"http://{host_header}"
    if server_address:
        host, port = server_address[:2]
        host = "127.0.0.1" if host in {"", "0.0.0.0"} else host
        return f"http://{host}:{port}"
    return "http://127.0.0.1:8765"


def make_handler(settings: Settings):
    vault = Vault(settings.vault_path)
    vault.init()
    index = Index(settings.runtime_path / "index.sqlite3")
    tokens = TokenStore(settings.runtime_path / "tokens.json")
    if settings.service_token not in {"", "dev-local-change-me"}:
        tokens.add_existing(settings.service_token, "local-user")

    class Handler(BaseHTTPRequestHandler):
        def _auth(self) -> bool:
            header = self.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
            result = tokens.verify(token)
            if not result.ok:
                return False
            client = self.client_address[0] if self.client_address else "unknown"
            return tokens.rate_limit(result.subject or "unknown", client)

        def _json(self, status: int, data: object) -> None:
            body = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length > settings.max_upload_bytes:
                raise ValueError("upload limit exceeded")
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = APP_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/manifest.json":
                self._json(200, manifest())
                return
            if parsed.path == "/sw.js":
                body = SERVICE_WORKER.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/icon.svg":
                body = ICON_SVG.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/qr.svg":
                value = parse_qs(parsed.query).get("url", [_request_url(self.headers.get("Host"), self.server.server_address)])[0]
                body = qr_svg(value).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path.startswith("/api/") and not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            if parsed.path == "/api/app-status":
                self._json(200, app_status(settings, vault, index, self.headers.get("Host"), self.server.server_address))
                return
            if parsed.path == "/api/health":
                self._json(200, {"vault": str(vault.root), "index": index.health()})
                return
            if parsed.path == "/api/model-status":
                self._json(200, discover_endpoint(settings, timeout=1.5))
                return
            if parsed.path == "/api/integrity":
                self._json(200, scan(vault))
                return
            if parsed.path == "/api/tasks":
                self._json(200, {"tasks": list_tasks(vault)})
                return
            if parsed.path == "/api/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                self._json(200, {"results": index.search(query or "source")})
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/") and not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                if parsed.path == "/api/capture-text":
                    payload = self._read_json()
                    result = capture_text(vault, payload["text"], channel=payload.get("channel", "pwa"), sender=payload.get("sender", "user"))
                    index.rebuild(vault)
                    self._json(200, result.__dict__)
                    return
                if parsed.path == "/api/upload":
                    payload = self._read_json()
                    result = handle_upload(vault, index, settings, payload)
                    self._json(200, result)
                    return
                if parsed.path == "/api/evaluate":
                    self._json(200, run_eval(settings, live_model=False))
                    return
                if parsed.path == "/api/revoke":
                    header = self.headers.get("Authorization", "")
                    token = header[7:] if header.startswith("Bearer ") else ""
                    tokens.revoke(token)
                    self._json(200, {"status": "revoked"})
                    return
            except Exception as exc:
                self._json(400, {"error": type(exc).__name__, "detail": str(exc)})
                return
            self._json(404, {"error": "not_found"})

    return Handler


def handle_upload(vault: Vault, index: Index, settings: Settings, payload: dict) -> dict:
    raw = base64.b64decode(payload["data_base64"], validate=True)
    if len(raw) > settings.max_upload_bytes:
        raise ValueError("upload limit exceeded")
    result = capture_binary(vault, raw, payload.get("filename", "upload.bin"), channel=payload.get("channel", "pwa"), sender=payload.get("sender", "user"))
    index.rebuild(vault)
    return result


def serve(settings: Settings, host: str, port: int) -> None:
    if settings.service_token in {"", "dev-local-change-me"}:
        raise ValueError("COGNI_SERVICE_TOKEN must be set to a non-default secret before starting the service")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("local phase service may only bind to loopback addresses")
    server = ThreadingHTTPServer((host, port), make_handler(settings))
    print(f"Cogni Life OS listening on http://{host}:{port}")
    print("Service token: [REDACTED]")
    server.serve_forever()
