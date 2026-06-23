from __future__ import annotations

import json
import base64
import os
import shutil
import socket
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .auth import TokenStore
from .config import Settings, persist_local_config, persist_vault_path
from .evaluation import run as run_eval
from .indexer import Index
from .ingest import capture_text
from .ingest import capture_binary
from .integrity import scan
from .markdown import parse_frontmatter
from .media import WHISPER_MODEL, extract
from .model_contract import chat, discover_endpoint
from .vault import Vault


ICLOUD_WARNING = "Cogni can use this folder, but file availability and sync conflicts remain controlled by iCloud. Keep backups and avoid simultaneous automated writes from multiple devices."
LOCAL_ONLY_PHONE_MESSAGE = "Phone access unavailable while the service is local-only."
LAN_WARNING = "LAN access exposes the service to devices on the same network."
REMOTE_NOT_CONFIGURED_MESSAGE = "Cross-device access is not configured."
ACCESS_MODE_LABELS = {
    "this-device": "This device only",
    "lan": "Local network",
    "tailscale": "Tailscale/private remote access",
    "custom": "Custom URL",
}


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
  <link rel="icon" href="/static/branding/cogni-chat-new-logo-round.ico" sizes="16x16 32x32" type="image/x-icon">
  <link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.jpg">
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
    [hidden] { display: none !important; }
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
    .brand-logo, .compact-logo { object-fit: cover; display: block; border-radius: 8px; box-shadow: var(--shadow); flex: 0 0 auto; }
    .brand-logo { width: 46px; height: 46px; }
    .compact-logo { width: 42px; height: 42px; }
    .login-hero { width: 78px; height: 78px; border-radius: 14px; object-fit: cover; box-shadow: var(--shadow); }
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
      margin: 0 auto; display: grid; grid-template-rows: auto minmax(0, 1fr) auto auto;
      border: 1px solid var(--line); border-radius: 8px; background: color-mix(in srgb, var(--panel) 94%, transparent);
      box-shadow: var(--shadow); overflow: hidden;
    }
    .chat-head {
      padding: 14px 16px; border-bottom: 1px solid var(--line);
      display: flex; justify-content: space-between; gap: 10px; align-items: center;
    }
    .messages { min-height: 0; overflow: auto; padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; align-content: start; }
    .msg { display: flex; flex-direction: column; gap: 8px; max-width: min(760px, 88%); }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 12px 14px; border-radius: 8px;
      background: var(--panel-2); color: var(--text); line-height: 1.45;
      border: 1px solid transparent;
    }
    .user .bubble { background: color-mix(in srgb, var(--accent) 15%, var(--panel)); color: var(--text); }
    .message-image {
      display: block; width: min(320px, 100%); max-height: 260px;
      object-fit: contain; border-radius: 8px; border: 1px solid var(--line); margin-bottom: 8px;
    }
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
    .icon-btn svg, .send svg, .mini-btn svg { width: 20px; height: 20px; stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round; }
    .icon-btn:focus-visible, .send:focus-visible, .mini-btn:focus-visible, .button:focus-visible, .nav a:focus-visible, .mobile-nav a:focus-visible {
      outline: 3px solid color-mix(in srgb, var(--brand) 55%, white);
      outline-offset: 2px;
    }
    .icon-btn[disabled] { opacity: .45; cursor: not-allowed; }
    .icon-btn.recording { background: var(--bad); border-color: color-mix(in srgb, #db5b51 48%, var(--line)); }
    .icon-btn.processing { background: var(--warn); border-color: color-mix(in srgb, #d59f1a 48%, var(--line)); }
    .icon-btn.error { background: var(--bad); border-color: color-mix(in srgb, #db5b51 68%, var(--line)); color: #8f2922; }
    .send { background: var(--brand); color: white; border-color: var(--brand); }
    .send.responding { background: #34413f; border-color: #34413f; }
    .attachment-preview {
      grid-column: 1 / -1; display: none; align-items: center; gap: 10px;
      min-width: 0; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2);
    }
    .attachment-preview.visible { display: flex; }
    .attachment-preview img {
      width: 72px; height: 72px; object-fit: cover; border-radius: 8px; border: 1px solid var(--line); flex: 0 0 auto;
    }
    .attachment-preview .preview-text { min-width: 0; overflow-wrap: anywhere; }
    .attachment-picker { position: relative; }
    .attachment-menu {
      position: absolute; left: 0; bottom: 54px; z-index: 4;
      width: 190px; display: none; gap: 4px; padding: 6px;
      border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
      box-shadow: var(--shadow);
    }
    .attachment-menu.visible { display: grid; }
    .menu-btn {
      border: 0; background: transparent; color: var(--text); cursor: pointer;
      min-height: 40px; border-radius: 8px; padding: 8px 10px; text-align: left;
    }
    .menu-btn:hover, .menu-btn:focus-visible { background: var(--panel-2); outline: none; }
    .voice-panel {
      border-top: 1px solid var(--line);
      padding: 8px 12px;
      display: none;
      gap: 10px;
      align-items: center;
      background: var(--panel);
    }
    .voice-panel.visible { display: flex; }
    .meter { height: 8px; min-width: 90px; flex: 1; border-radius: 999px; background: var(--panel-2); overflow: hidden; border: 1px solid var(--line); }
    .meter > span { display: block; height: 100%; width: 0%; background: var(--brand); }
    .thinking-dots { display: inline-flex; align-items: center; gap: 4px; min-width: 42px; min-height: 21px; vertical-align: middle; }
    .thinking-dots span {
      width: 7px; height: 7px; border-radius: 99px; background: currentColor;
      opacity: .35; animation: thinkingPulse 1.15s ease-in-out infinite;
    }
    .thinking-dots span:nth-child(2) { animation-delay: .15s; }
    .thinking-dots span:nth-child(3) { animation-delay: .3s; }
    @keyframes thinkingPulse {
      0%, 80%, 100% { transform: translateY(0); opacity: .35; }
      40% { transform: translateY(-3px); opacity: 1; }
    }
    .playback-bar {
      display: none; gap: 6px; align-items: center; justify-content: flex-start;
      padding: 6px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
    }
    .playback-bar.visible { display: inline-flex; }
    .playback-label { color: var(--muted); font-size: 13px; margin-right: 2px; }
    .speech-controls { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
    .mini-btn {
      border: 1px solid var(--line); background: var(--panel-2); color: var(--text);
      min-width: 44px; width: 44px; min-height: 44px; height: 44px;
      border-radius: 8px; padding: 0; cursor: pointer; display: grid; place-items: center;
    }
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
      .chat-head { padding: 10px 14px; align-items: flex-start; }
      .chat-head > .row { gap: 8px; }
      .chat-head .pill { max-width: 118px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .chat-head .small { display: none; }
      .messages { padding: 14px; }
      .composer { padding-bottom: calc(74px + env(safe-area-inset-bottom)); }
      .playback-bar { padding: 6px; justify-content: flex-end; }
      .playback-label { display: none; }
      .attachment-preview img { width: 58px; height: 58px; }
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
      <img class="brand-logo" src="/static/branding/cogni-logo.jpeg" alt="Cogni Life OS logo">
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
      <div class="qr" id="launchQr" hidden><img id="qrImage" alt="QR code for LAN PWA URL"></div>
      <div class="small muted" id="phoneUrl">Phone URL unavailable</div>
      <div class="small muted" id="modelEndpoint">Model endpoint unavailable</div>
      <div class="warning" id="phoneWarning" hidden>Phone access unavailable while the service is local-only.</div>
    </section>
  </aside>

  <main class="main">
    <header class="topbar">
      <div class="brand"><img class="compact-logo" src="/static/branding/cogni-chat-new-logo-round.ico" alt="Cogni"><div><h1>Cogni Life OS</h1><p id="mobileSub">Locked</p></div></div>
    </header>
    <div class="view">
      <section id="chat" class="screen active" data-title="Chat">
        <div class="chat-shell">
          <div class="chat-head">
            <div>
              <strong>Cogni</strong>
              <div class="small muted">Search-backed conversation with your local vault</div>
            </div>
            <div class="row">
              <div class="pill"><span class="dot warn" id="chatModelDot"></span><span id="activeModel">Model unavailable</span></div>
              <button class="mini-btn" id="speakerBtn" type="button" title="Enable spoken replies" aria-label="Enable spoken replies">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/></svg>
              </button>
              <button class="mini-btn" id="clearChatBtn" type="button" title="Clear conversation" aria-label="Clear conversation">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>
              </button>
            </div>
          </div>
          <div class="messages" id="messages" aria-live="polite"></div>
          <div class="voice-panel" id="voicePanel">
            <strong id="recordingState">Recording</strong>
            <span class="small muted" id="recordingDuration">0.0s</span>
            <div class="meter" aria-label="Audio level"><span id="audioLevel"></span></div>
            <button class="mini-btn" id="cancelVoiceBtn" type="button" title="Cancel recording" aria-label="Cancel recording">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
          <form class="composer" id="chatForm">
            <div class="attachment-preview" id="attachmentPreview">
              <img id="attachmentPreviewImage" alt="Selected image preview" hidden>
              <div class="preview-text small"><strong id="attachmentPreviewTitle">Attachment selected</strong><div class="muted" id="attachmentPreviewMeta"></div></div>
              <button class="mini-btn" id="removeAttachmentBtn" type="button" title="Remove selected attachment" aria-label="Remove selected attachment">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
              </button>
            </div>
            <div class="attachment-picker">
              <button class="icon-btn" id="attachmentBtn" type="button" title="Add attachment" aria-label="Add attachment" aria-haspopup="menu" aria-expanded="false">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21.4 11.6-8.8 8.8a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 0 1-2.8-2.8l8.8-8.8"/></svg>
              </button>
              <div class="attachment-menu" id="attachmentMenu" role="menu">
                <button class="menu-btn" type="button" role="menuitem" data-attach="camera">Take photo</button>
                <button class="menu-btn" type="button" role="menuitem" data-attach="photo">Choose photo</button>
                <button class="menu-btn" type="button" role="menuitem" data-attach="document">Choose document</button>
              </div>
              <input class="sr-only" id="chatCamera" type="file" accept="image/*" capture="environment">
              <input class="sr-only" id="chatPhoto" type="file" accept="image/*">
              <input class="sr-only" id="chatDocument" type="file" accept="image/*,.pdf,.txt,.md,.markdown,.docx,.wav,.mp3,.m4a,.flac,.ogg,.webm,application/pdf,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document,audio/*">
            </div>
            <button class="icon-btn" id="voiceBtn" type="button" title="Hold to talk" aria-label="Hold to talk">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M19 11a7 7 0 0 1-14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></svg>
            </button>
            <textarea id="chatInput" rows="1" placeholder="Ask Cogni..." autocomplete="off"></textarea>
            <button class="send" id="sendBtn" type="submit" title="Send" aria-label="Send">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></svg>
            </button>
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
            <h2>Vault</h2>
            <label class="stack small">Vault path<input id="vaultPathInput" placeholder="/absolute/path/to/vault"></label>
            <div class="row"><button class="button secondary" id="validateVaultBtn" type="button">Validate</button><button class="button" id="saveVaultBtn" type="button">Save</button><button class="button secondary" id="rebuildIndexBtn" type="button">Rebuild index</button></div>
            <div class="item small muted" id="vaultConfigResult">Vault status unavailable.</div>
          </div>
          <div class="panel stack">
            <h2>Model</h2>
            <div class="item"><strong>Cogni-Brain</strong><div class="small muted" id="settingsModelState">Model status unavailable.</div></div>
            <button class="button secondary" id="modelCheckBtn">Check endpoint</button>
            <div id="modelDiagOut" class="small muted"></div>
          </div>
          <div class="panel stack">
            <h2>Voice</h2>
            <div class="item"><strong>Spoken replies</strong><div class="small muted" id="voiceState">Checking local transcription and browser playback.</div></div>
          </div>
          <div class="panel stack">
            <h2>Access</h2>
            <label class="stack small">Access mode
              <select id="accessModeSelect">
                <option value="this-device">This device only</option>
                <option value="lan">Local network</option>
                <option value="tailscale">Tailscale/private remote access</option>
                <option value="custom">Custom URL</option>
              </select>
            </label>
            <label class="stack small">Public base URL<input id="publicBaseUrlInput" placeholder="https://your-device.tailnet.ts.net"></label>
            <div class="row"><button class="button secondary" id="validateAccessBtn" type="button">Validate URL</button><button class="button" id="saveAccessBtn" type="button">Save access</button><button class="button secondary" id="copyPublicUrlBtn" type="button">Copy URL</button></div>
            <div class="item"><strong>Service mode</strong><div class="small muted" id="remoteState">Loopback-only by default.</div></div>
            <div class="item"><strong>Cogni Life OS service address</strong><div class="small muted" id="serviceAddressState">Unavailable</div></div>
            <div class="item"><strong>Reachability/configuration</strong><div class="small muted" id="accessConfigState">Unavailable</div></div>
            <div class="item"><strong>Phone URL</strong><div class="small muted" id="settingsPhoneUrl">Unavailable</div></div>
            <div class="qr" id="settingsQr" hidden><img id="settingsQrImage" alt="QR code for LAN PWA URL"></div>
            <div class="warning" id="settingsAccessWarning">Phone access unavailable while the service is local-only.</div>
            <div class="small muted" id="lanModeHint"></div>
          </div>
          <div class="panel stack">
            <h2>Diagnostics</h2>
            <div id="settingsStatus" class="list"></div>
            <button class="button secondary" id="refreshStatusBtn" title="Refresh service status" aria-label="Refresh service status">Refresh service status</button>
            <button class="button secondary" id="advancedBtn">Advanced diagnostics</button>
            <button class="button secondary" id="integrityBtn">Run integrity</button>
            <button class="button secondary" id="evaluateBtn">Run evaluation</button>
            <div id="integrityOut" class="small muted"></div>
            <div id="evaluateOut" class="small muted"></div>
            <details><summary>Raw diagnostics</summary><pre id="rawDiagnostics"></pre></details>
            <button class="button secondary" id="logoutBtn">Forget service token</button>
          </div>
        </div>
      </section>

      <section id="advanced" class="screen" data-title="Advanced">
        <div class="panel stack">
          <div class="row"><h2>Advanced</h2><button class="button secondary" id="backSettingsBtn">Settings</button></div>
          <div class="panel-grid">
            <div class="panel stack"><h3>Indexing</h3><div id="indexAdmin" class="small muted">Index rebuild runs after capture, upload, and vault changes.</div></div>
            <div class="panel stack"><h3>Backup</h3><div class="small muted">Use the local backup script or CLI for now.</div></div>
            <div class="panel stack"><h3>Operations</h3><div class="small muted">Safe-operation controls remain bounded by local policy.</div></div>
          </div>
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
    <div class="brand"><img class="login-hero" src="/static/branding/cogni-logo.jpeg" alt="Cogni Life OS logo"><div><h1>Cogni Life OS</h1><p>Authenticate to your local service</p></div></div>
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
  spokenReplies: resolveSpokenPreference(),
  status: null,
  messages: [],
  pendingProposal: null,
  pendingAttachment: null,
  pendingRequest: null,
  recorder: null,
  recording: false,
  cancelRecording: false,
  recordingStarted: 0,
  recordingTimer: null,
  audioContext: null,
  audioSource: null,
  audioProcessor: null,
  audioStream: null,
  audioSamples: [],
  audioSampleRate: 16000,
  lastSpokenText: "",
  lastSpokenMessageId: null,
  activeSpeech: false,
  modelResponding: false
};
const $ = (id) => document.getElementById(id);
const views = ["chat", "capture", "knowledge", "tasks", "settings", "advanced"];
const ICON_SEND = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></svg>';
const ICON_STOP_GENERATION = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10v10H7z"/></svg>';
const ICON_SPEAKER_ON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M16 8a5 5 0 0 1 0 8"/><path d="M19 5a9 9 0 0 1 0 14"/></svg>';
const ICON_SPEAKER_MUTED = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/></svg>';
const PLAYBACK_CONTROLS_HTML = `
  <div class="playback-bar visible" aria-live="polite">
    <span class="playback-label">Spoken reply</span>
    <button class="mini-btn" type="button" data-speech-action="pause" title="Pause speech" aria-label="Pause speech">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14"/><path d="M16 5v14"/></svg>
    </button>
    <button class="mini-btn" type="button" data-speech-action="resume" title="Resume speech" aria-label="Resume speech">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
    </button>
    <button class="mini-btn" type="button" data-speech-action="stop" title="Stop speech" aria-label="Stop speech">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10v10H7z"/></svg>
    </button>
    <button class="mini-btn" type="button" data-speech-action="replay" title="Replay speech" aria-label="Replay speech">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/></svg>
    </button>
  </div>`;
function resolveSpokenPreference() {
  const stored = localStorage.getItem("cogni_spoken_replies");
  if (stored === "true" || stored === "false") return stored === "true";
  const legacy = localStorage.getItem("cogni_conversation_mode");
  return legacy === "voice" || legacy === "listen";
}
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
function welcomeMessage() {
  return "Welcome back. I can search your vault, capture memories, preserve uploads, and show citations.";
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
  $("phoneUrl").textContent = status.service.phone_url || status.service.phone_warning || "Cross-device access is not configured.";
  $("modelEndpoint").textContent = `${status.model.endpoint} . ${status.model.endpoint_status}`;
  $("remoteState").textContent = status.service.mode_label || status.service.mode;
  $("voiceState").textContent = `STT: ${status.voice.stt.provider} (${status.voice.stt.status}). TTS: ${status.voice.tts.provider} (${status.voice.tts.status}).`;
  $("phoneWarning").hidden = Boolean(status.service.phone_url);
  $("phoneWarning").textContent = status.service.warning || status.service.phone_warning || "";
  $("launchQr").hidden = !status.service.phone_url;
  setDot("serviceDot", "ok"); setDot("vaultDot", status.vault.status === "ready" ? "ok" : "bad");
  setDot("indexDot", "ok"); setDot("safeDot", "ok"); setDot("launchDot", status.service.phone_url ? "ok" : "warn");
  setDot("modelDot", status.model.endpoint_status === "online" ? "ok" : "warn");
  setDot("chatModelDot", status.model.endpoint_status === "online" ? "ok" : "warn");
  renderSettings();
  if (status.service.phone_url) $("qrImage").src = "/qr.svg?url=" + encodeURIComponent(status.service.phone_url);
}
async function refreshStatus() {
  const status = await api("/api/app-status");
  renderStatus(status);
  $("rawDiagnostics").textContent = JSON.stringify(status, null, 2);
}
function addMessage(role, htmlContent, extra="", options={}) {
  const item = Object.assign({
    id: "msg-" + Date.now() + "-" + Math.random().toString(16).slice(2),
    role,
    htmlContent,
    extra,
    ts: new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})
  }, options);
  state.messages.push(item);
  renderMessages();
  return item.id;
}
function updateMessage(id, updates) {
  const item = state.messages.find(message => message.id === id);
  if (!item) return;
  Object.assign(item, updates);
  renderMessages();
}
function removeMessage(id) {
  state.messages = state.messages.filter(message => message.id !== id);
  renderMessages();
}
function thinkingHtml() {
  return '<span class="sr-only">Cogni is thinking</span><span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
}
function messageImageHtml(image) {
  if (!image) return "";
  return `<img class="message-image" src="${escapeHtml(image.url)}" alt="${escapeHtml(image.alt || "Attached image")}">`;
}
function renderMessages() {
  $("messages").innerHTML = state.messages.map(m => `
    <article class="msg ${m.role}">
      <div class="bubble">${messageImageHtml(m.image)}${m.htmlContent}</div>
      ${m.extra || ""}
      ${m.playback ? PLAYBACK_CONTROLS_HTML : ""}
      <div class="meta">${m.role === "user" ? "You" : "Cogni"} . ${m.ts}</div>
    </article>
  `).join("");
  $("messages").scrollTop = $("messages").scrollHeight;
  bindPlaybackControls();
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
async function sendChat(text, attachment=null) {
  const userOptions = attachment && attachment.kind === "image" ? {image: {url: attachment.previewUrl, alt: attachment.file.name}} : {};
  addMessage("user", escapeHtml(text || (attachment && attachment.kind === "image" ? "Image attached" : "")), "", userOptions);
  const placeholderId = addMessage("assistant", thinkingHtml(), "", {thinking: true});
  const controller = new AbortController();
  state.pendingRequest = controller;
  setSendResponding(true);
  try {
    const multimodal = attachment && attachment.kind === "image" ? await imagePayload(attachment.file) : null;
    const data = await api("/api/chat", {method:"POST", headers:{"Content-Type":"application/json"}, signal: controller.signal, body: JSON.stringify({message:text || "Please inspect the attached image.", input: multimodal ? "image" : "text", image: multimodal})});
    updateMessage(placeholderId, {htmlContent: escapeHtml(data.reply || "No reply returned."), extra: sourcesHtml(data.sources || []), thinking: false});
    if (data.status !== "completed") {
      addMessage("assistant", escapeHtml(data.detail || "Cogni-Brain is unavailable."), proposalHtml(text));
    } else {
      speakIfEnabled(data.reply || "", placeholderId);
    }
  } catch (err) {
    removeMessage(placeholderId);
    if (err.name === "AbortError") return;
    throw err;
  } finally {
    if (state.pendingRequest === controller) state.pendingRequest = null;
    setSendResponding(false);
  }
}
async function searchVault(query) {
  const data = await api("/api/search?q=" + encodeURIComponent(query || "source"));
  return data.results || [];
}
async function captureNote(text, channel="pwa") {
  return await api("/api/capture-text", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text, channel, sender:"user"})});
}
async function readFileDataUrl(file) {
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
  return String(dataUrl);
}
async function imagePayload(file) {
  const dataUrl = await readFileDataUrl(file);
  const data_base64 = dataUrl.split(",", 2)[1] || "";
  return {filename: file.name, mime_type: file.type || "image/*", data_base64};
}
async function uploadFile(file) {
  const dataUrl = await readFileDataUrl(file);
  const data_base64 = String(dataUrl).split(",", 2)[1] || "";
  return await api("/api/upload", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({filename:file.name, data_base64, channel:"pwa", sender:"user"})});
}
async function transcribeAudio(wavBytes, durationSeconds) {
  const binary = Array.from(new Uint8Array(wavBytes), byte => String.fromCharCode(byte)).join("");
  return await api("/api/transcribe", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({filename:"voice.wav", duration_seconds: durationSeconds, data_base64:btoa(binary)})});
}
function canSpeak() {
  return "speechSynthesis" in window && state.spokenReplies;
}
function speechText(text) {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/https?:\/\/\S+/g, " link ")
    .replace(/\[[^\]]+\]\([^)]*\)/g, " ")
    .replace(/\[[0-9]+\]/g, " ")
    .replace(/[`*_#>{}\[\]]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
function stopSpeech() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  state.activeSpeech = false;
}
function setSpeakerEnabled(enabled) {
  state.spokenReplies = Boolean(enabled);
  localStorage.setItem("cogni_spoken_replies", state.spokenReplies ? "true" : "false");
  updateSpeakerButton();
  if (!state.spokenReplies) stopSpeech();
}
function updateSpeakerButton() {
  const button = $("speakerBtn");
  if (!button) return;
  button.innerHTML = state.spokenReplies ? ICON_SPEAKER_ON : ICON_SPEAKER_MUTED;
  button.title = state.spokenReplies ? "Mute spoken replies" : "Enable spoken replies";
  button.setAttribute("aria-label", state.spokenReplies ? "Mute spoken replies" : "Enable spoken replies");
}
function bindPlaybackControls() {
  document.querySelectorAll("[data-speech-action]").forEach(button => {
    if (button.dataset.bound === "true") return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const action = button.dataset.speechAction;
      if (action === "pause" && "speechSynthesis" in window) window.speechSynthesis.pause();
      if (action === "resume" && "speechSynthesis" in window) window.speechSynthesis.resume();
      if (action === "stop") stopSpeech();
      if (action === "replay") speakIfEnabled(state.lastSpokenText, state.lastSpokenMessageId);
    });
  });
}
function setSendResponding(isResponding) {
  state.modelResponding = isResponding;
  const button = $("sendBtn");
  button.classList.toggle("responding", isResponding);
  button.title = isResponding ? "Stop generation" : "Send";
  button.setAttribute("aria-label", isResponding ? "Stop generation" : "Send");
  button.innerHTML = isResponding ? ICON_STOP_GENERATION : ICON_SEND;
}
function setMicState(name) {
  const button = $("voiceBtn");
  button.classList.remove("recording", "processing", "error");
  if (name !== "idle") button.classList.add(name);
  const labels = {
    idle: "Hold to talk",
    recording: "Recording. Release to submit",
    processing: "Processing voice",
    error: "Microphone or transcription error"
  };
  button.title = labels[name] || labels.idle;
  button.setAttribute("aria-label", labels[name] || labels.idle);
}
function clearPendingAttachment() {
  if (state.pendingAttachment && state.pendingAttachment.previewUrl) URL.revokeObjectURL(state.pendingAttachment.previewUrl);
  state.pendingAttachment = null;
  $("chatCamera").value = "";
  $("chatPhoto").value = "";
  $("chatDocument").value = "";
  renderAttachmentPreview();
}
function renderAttachmentPreview() {
  const preview = $("attachmentPreview");
  const image = $("attachmentPreviewImage");
  const title = $("attachmentPreviewTitle");
  const meta = $("attachmentPreviewMeta");
  const attachment = state.pendingAttachment;
  preview.classList.toggle("visible", Boolean(attachment));
  if (!attachment) {
    image.hidden = true;
    image.removeAttribute("src");
    title.textContent = "Attachment selected";
    meta.textContent = "";
    return;
  }
  title.textContent = attachment.kind === "image" ? "Image ready to send" : "Document ready";
  meta.textContent = attachment.kind === "image" ? attachment.file.name : `${attachment.file.name} . ${attachment.file.type || "unknown type"}`;
  if (attachment.kind === "image") {
    image.hidden = false;
    image.src = attachment.previewUrl;
  } else {
    image.hidden = true;
    image.removeAttribute("src");
  }
}
function setPendingImage(file) {
  clearPendingAttachment();
  state.pendingAttachment = {kind: "image", file, previewUrl: URL.createObjectURL(file)};
  renderAttachmentPreview();
}
function setPendingDocument(file) {
  clearPendingAttachment();
  state.pendingAttachment = {kind: "document", file, previewUrl: ""};
  renderAttachmentPreview();
}
function stopPendingRequest() {
  if (state.pendingRequest) {
    state.pendingRequest.abort();
    state.pendingRequest = null;
  }
  setSendResponding(false);
}
function clearConversation() {
  if (!confirm("Clear the current browser conversation? Vault sources, tasks, and model history outside this session will not be deleted.")) return;
  stopSpeech();
  stopPendingRequest();
  clearPendingAttachment();
  state.messages = [];
  state.lastSpokenText = "";
  state.lastSpokenMessageId = null;
  addMessage("assistant", welcomeMessage());
}
function speakIfEnabled(text, messageId=null) {
  state.lastSpokenText = text || state.lastSpokenText;
  state.lastSpokenMessageId = messageId || state.lastSpokenMessageId;
  if (!canSpeak()) return;
  if (messageId) updateMessage(messageId, {playback: true});
  stopSpeech();
  const clean = speechText(text);
  if (!clean) return;
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onstart = () => { state.activeSpeech = true; if (messageId) updateMessage(messageId, {playback: true}); };
  utterance.onend = () => { state.activeSpeech = false; if (messageId) updateMessage(messageId, {playback: true}); };
  utterance.onerror = () => { state.activeSpeech = false; if (messageId) updateMessage(messageId, {playback: true}); };
  window.speechSynthesis.speak(utterance);
}
function encodeWav(samples, sampleRate) {
  const length = samples.reduce((sum, item) => sum + item.length, 0);
  const pcm = new Int16Array(length);
  let offset = 0;
  for (const chunk of samples) {
    for (let i = 0; i < chunk.length; i++) {
      const value = Math.max(-1, Math.min(1, chunk[i]));
      pcm[offset++] = value < 0 ? value * 0x8000 : value * 0x7fff;
    }
  }
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  const write = (pos, value) => { for (let i = 0; i < value.length; i++) view.setUint8(pos + i, value.charCodeAt(i)); };
  write(0, "RIFF"); view.setUint32(4, 36 + pcm.length * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) view.setInt16(44 + i * 2, pcm[i], true);
  return buffer;
}
async function startRecording(event) {
  event.preventDefault();
  if (state.recording) return;
  stopSpeech();
  state.cancelRecording = false;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    state.audioSamples = [];
    state.audioSampleRate = context.sampleRate;
    processor.onaudioprocess = event => {
      const input = event.inputBuffer.getChannelData(0);
      state.audioSamples.push(new Float32Array(input));
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      $("audioLevel").style.width = Math.min(100, Math.sqrt(sum / input.length) * 240) + "%";
    };
    source.connect(processor);
    processor.connect(context.destination);
    state.audioContext = context; state.audioSource = source; state.audioProcessor = processor; state.audioStream = stream;
    state.recording = true; state.recordingStarted = Date.now();
    $("voicePanel").classList.add("visible");
    setMicState("recording");
    $("recordingState").textContent = "Recording";
    state.recordingTimer = setInterval(() => {
      $("recordingDuration").textContent = ((Date.now() - state.recordingStarted) / 1000).toFixed(1) + "s";
    }, 100);
  } catch (err) {
    setMicState("error");
    setTimeout(() => setMicState("idle"), 1800);
    addMessage("assistant", "Microphone unavailable.", `<div class="error-card">${escapeHtml(err.message || err)}</div>`);
  }
}
async function stopRecording(submit=true) {
  if (!state.recording) return;
  const duration = (Date.now() - state.recordingStarted) / 1000;
  state.recording = false;
  clearInterval(state.recordingTimer);
  $("voicePanel").classList.remove("visible");
  setMicState("idle");
  if (state.audioProcessor) state.audioProcessor.disconnect();
  if (state.audioSource) state.audioSource.disconnect();
  if (state.audioStream) state.audioStream.getTracks().forEach(track => track.stop());
  if (state.audioContext) await state.audioContext.close();
  const samples = state.audioSamples;
  state.audioSamples = [];
  if (!submit || state.cancelRecording) {
    addMessage("assistant", "Voice recording discarded.");
    return;
  }
  if (duration < 0.35 || !samples.length) {
    setMicState("error");
    setTimeout(() => setMicState("idle"), 1800);
    addMessage("assistant", "Recording was empty.", `<div class="error-card">Hold the microphone while speaking, then release to submit.</div>`);
    return;
  }
  try {
    setMicState("processing");
    addMessage("assistant", "Transcribing locally with whisper-cpp...");
    const result = await transcribeAudio(encodeWav(samples, state.audioSampleRate), duration);
    if (result.status !== "complete" || !result.transcript) throw new Error(result.error_details || result.error_code || "No transcript returned");
    setMicState("idle");
    addMessage("user", escapeHtml(result.transcript));
    const placeholderId = addMessage("assistant", thinkingHtml(), "", {thinking: true});
    const controller = new AbortController();
    state.pendingRequest = controller;
    setSendResponding(true);
    try {
      const data = await api("/api/chat", {method:"POST", headers:{"Content-Type":"application/json"}, signal: controller.signal, body: JSON.stringify({message:result.transcript, input:"voice"})});
      updateMessage(placeholderId, {htmlContent: escapeHtml(data.reply || "No reply returned."), extra: sourcesHtml(data.sources || []), thinking: false});
      if (data.status === "completed") speakIfEnabled(data.reply || "", placeholderId);
    } catch (err) {
      removeMessage(placeholderId);
      if (err.name !== "AbortError") throw err;
    } finally {
      if (state.pendingRequest === controller) state.pendingRequest = null;
    }
  } catch (err) {
    setMicState("error");
    setTimeout(() => setMicState("idle"), 1800);
    addMessage("assistant", "Voice turn failed.", `<div class="error-card">${escapeHtml(err.message || err)}</div>`);
  } finally {
    setSendResponding(false);
  }
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
  $("vaultPathInput").value = $("vaultPathInput").value || state.status.vault.path;
  $("settingsModelState").textContent = `${state.status.model.name} . ${state.status.model.endpoint_status}`;
  $("accessModeSelect").value = state.status.service.access_mode || state.status.service.mode || "this-device";
  $("publicBaseUrlInput").value = $("publicBaseUrlInput").value || state.status.service.public_base_url || "";
  $("settingsPhoneUrl").textContent = state.status.service.phone_url || state.status.service.phone_warning || "Cross-device access is not configured.";
  $("serviceAddressState").textContent = state.status.service.local_url;
  $("accessConfigState").textContent = state.status.service.phone_url ? (state.status.service.configured_for_running_service ? "Configured for this running service." : "URL selected, but this running service may need a bind/port or reverse-proxy restart.") : "Cross-device access is not configured.";
  $("settingsQr").hidden = !state.status.service.phone_url;
  if (state.status.service.phone_url) $("settingsQrImage").src = "/qr.svg?url=" + encodeURIComponent(state.status.service.phone_url);
  $("settingsAccessWarning").textContent = state.status.service.warning || state.status.service.phone_warning || "";
  $("lanModeHint").textContent = `Running: ${state.status.service.local_url}. Configured bind: ${state.status.service.configured_bind_host}:${state.status.service.configured_port}. Changing bind host or port requires a service restart. Cogni-Brain model endpoint is separate.`;
  const vault = state.status.vault;
  $("vaultConfigResult").innerHTML = `
    <strong>${escapeHtml(vault.status)}</strong>
    <div>Indexed notes: ${escapeHtml(state.status.index.note_count || 0)}</div>
    <div>Read: ${escapeHtml(vault.readable ? "yes" : "no")} . Write: ${escapeHtml(vault.writable ? "yes" : "no")}</div>
    <div>Last successful index: ${escapeHtml(state.status.index.last_successful_index_time || "unknown")}</div>
    ${vault.icloud ? `<div>${escapeHtml(vault.icloud_warning)}</div>` : ""}
  `;
  $("settingsStatus").innerHTML = [
    ["Service", state.status.service.status],
    ["Cogni service address", state.status.service.phone_url || state.status.service.local_url],
    ["Access mode", state.status.service.mode_label || state.status.service.mode],
    ["Cogni-Brain model endpoint", state.status.model.endpoint],
    ["Vault", state.status.vault.path],
    ["Index", `${state.status.index.note_count || 0} notes`],
    ["Safe operations", state.status.safe_operations.status]
  ].map(([k,v]) => `<div class="item"><strong>${escapeHtml(k)}</strong><div class="small muted">${escapeHtml(v)}</div></div>`).join("");
}
async function validateAccessConfig() {
  const result = await api("/api/access/validate", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({mode:$("accessModeSelect").value, public_base_url:$("publicBaseUrlInput").value})});
  $("accessConfigState").textContent = result.valid ? "Access settings are valid." : (result.error || "Access settings are invalid.");
  return result;
}
async function saveAccessConfig() {
  const result = await api("/api/access/save", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({mode:$("accessModeSelect").value, public_base_url:$("publicBaseUrlInput").value})});
  $("accessConfigState").textContent = result.restart_required ? "Saved. Restart required for bind host or port changes." : "Saved.";
  await refreshStatus();
}
async function copyPublicUrl() {
  const value = state.status && state.status.service ? state.status.service.phone_url : "";
  if (!value) {
    $("accessConfigState").textContent = "Cross-device access is not configured.";
    return;
  }
  await navigator.clipboard.writeText(value);
  $("accessConfigState").textContent = "Copied.";
}
async function validateVaultPath() {
  const result = await api("/api/vault/validate", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({path:$("vaultPathInput").value})});
  $("vaultPathInput").value = result.path || $("vaultPathInput").value;
  $("vaultConfigResult").innerHTML = `<strong>${result.valid ? "Valid vault path" : "Vault path rejected"}</strong><div>${escapeHtml((result.errors || []).join(" ") || "Ready to save.")}</div>${result.icloud ? `<div>${escapeHtml(result.icloud_warning)}</div>` : ""}`;
  return result;
}
async function saveVaultPath() {
  const current = state.status && state.status.vault ? state.status.vault.path : "";
  const requested = $("vaultPathInput").value.trim();
  let confirmed = false;
  if (current && requested && current !== requested && (state.status.index.note_count || 0) > 0) {
    confirmed = confirm("Switch vaults and rebuild disposable indexes? Source files will not be moved, copied, or deleted.");
    if (!confirmed) return;
  }
  const result = await api("/api/vault/save", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({path:requested, confirm_switch:confirmed})});
  $("vaultConfigResult").innerHTML = `<strong>Vault saved</strong><div>${escapeHtml(result.path)}</div><div>Rebuilt ${escapeHtml(result.index_count)} indexed notes.</div>${result.icloud ? `<div>${escapeHtml(result.icloud_warning)}</div>` : ""}`;
  await refreshStatus();
}
async function rebuildIndex() {
  const result = await api("/api/index/rebuild", {method:"POST"});
  $("vaultConfigResult").innerHTML = `<strong>Index rebuilt</strong><div>${escapeHtml(result.count)} indexed notes.</div>`;
  await refreshStatus();
}
function toggleAttachmentMenu(force) {
  const menu = $("attachmentMenu");
  const visible = force === undefined ? !menu.classList.contains("visible") : Boolean(force);
  menu.classList.toggle("visible", visible);
  $("attachmentBtn").setAttribute("aria-expanded", visible ? "true" : "false");
}
function showError(target, err) {
  $(target).innerHTML = `<div class="error-card"><strong>Error</strong><div class="small">${escapeHtml(err.message || err)}</div></div>`;
}
async function bootstrap() {
  updateSpeakerButton();
  $("tokenInput").value = state.token;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    $("voiceBtn").disabled = true;
    $("voiceBtn").title = "Microphone recording is unavailable in this browser";
  }
  if (!("speechSynthesis" in window)) {
    $("speakerBtn").disabled = true;
    $("speakerBtn").title = "Spoken replies are unavailable in this browser";
  }
  if (state.token) {
    try {
      await refreshStatus();
      $("login").classList.add("hidden");
      addMessage("assistant", welcomeMessage());
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
  if (state.modelResponding) {
    stopPendingRequest();
    return;
  }
  const text = $("chatInput").value.trim();
  const attachment = state.pendingAttachment;
  if (!text && !attachment) return;
  if (attachment && attachment.kind === "document") {
    addMessage("user", `Attached document: ${escapeHtml(attachment.file.name)}`);
    try {
      const result = await uploadFile(attachment.file);
      addMessage("assistant", `Preserved ${escapeHtml(attachment.file.name)} as a vault source.`, sourcesHtml([{title: result.source_id, path: result.source_path, score: 1, reasons:["uploaded_source"]}]));
      await refreshStatus();
    } catch (err) { addMessage("assistant", "Upload failed.", `<div class="error-card">${escapeHtml(err.message)}</div>`); }
    clearPendingAttachment();
    return;
  }
  $("chatInput").value = "";
  state.pendingAttachment = null;
  $("chatCamera").value = "";
  $("chatPhoto").value = "";
  $("chatDocument").value = "";
  renderAttachmentPreview();
  try { await sendChat(text, attachment); } catch (err) { addMessage("assistant", "Something went wrong.", `<div class="error-card">${escapeHtml(err.message)}</div>`); }
});
function handlePhotoSelection(event) {
  const file = event.target.files[0];
  if (!file) return;
  setPendingImage(file);
  toggleAttachmentMenu(false);
}
$("chatCamera").addEventListener("change", handlePhotoSelection);
$("chatPhoto").addEventListener("change", handlePhotoSelection);
$("chatDocument").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if ((file.type || "").startsWith("image/")) setPendingImage(file);
  else setPendingDocument(file);
  toggleAttachmentMenu(false);
});
$("attachmentBtn").addEventListener("click", () => toggleAttachmentMenu());
document.querySelectorAll("[data-attach]").forEach(button => button.addEventListener("click", () => {
  const kind = button.dataset.attach;
  if (kind === "camera") $("chatCamera").click();
  if (kind === "photo") $("chatPhoto").click();
  if (kind === "document") $("chatDocument").click();
}));
document.addEventListener("click", event => {
  if (!$("attachmentMenu").contains(event.target) && !$("attachmentBtn").contains(event.target)) toggleAttachmentMenu(false);
});
$("removeAttachmentBtn").addEventListener("click", clearPendingAttachment);
$("speakerBtn").addEventListener("click", () => setSpeakerEnabled(!state.spokenReplies));
$("clearChatBtn").addEventListener("click", clearConversation);
$("voiceBtn").addEventListener("pointerdown", startRecording);
$("voiceBtn").addEventListener("pointerup", () => stopRecording(true));
$("voiceBtn").addEventListener("pointercancel", () => { state.cancelRecording = true; stopRecording(false); });
$("voiceBtn").addEventListener("contextmenu", event => event.preventDefault());
$("cancelVoiceBtn").addEventListener("click", () => { state.cancelRecording = true; stopRecording(false); });
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
$("refreshStatusBtn").addEventListener("click", refreshStatus);
$("validateVaultBtn").addEventListener("click", async () => { try { await validateVaultPath(); } catch (err) { $("vaultConfigResult").textContent = err.message; } });
$("saveVaultBtn").addEventListener("click", async () => { try { await saveVaultPath(); } catch (err) { $("vaultConfigResult").textContent = err.message; } });
$("rebuildIndexBtn").addEventListener("click", async () => { try { await rebuildIndex(); } catch (err) { $("vaultConfigResult").textContent = err.message; } });
$("validateAccessBtn").addEventListener("click", async () => { try { await validateAccessConfig(); } catch (err) { $("accessConfigState").textContent = err.message; } });
$("saveAccessBtn").addEventListener("click", async () => { try { await saveAccessConfig(); } catch (err) { $("accessConfigState").textContent = err.message; } });
$("copyPublicUrlBtn").addEventListener("click", async () => { try { await copyPublicUrl(); } catch (err) { $("accessConfigState").textContent = err.message; } });
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
const SHELL = ["/", "/manifest.json", "/static/branding/cogni-logo.jpeg", "/static/branding/cogni-chat-new-logo-round.ico", "/static/icons/cogni-pwa-192.jpg"];
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

STATIC_ROOT = Path(__file__).resolve().parent / "static"


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
            {"src": "/static/branding/cogni-chat-new-logo-round.ico", "sizes": "16x16 32x32", "type": "image/x-icon", "purpose": "any"},
            {"src": "/static/icons/cogni-pwa-192.jpg", "sizes": "192x192", "type": "image/jpeg", "purpose": "any maskable"},
            {"src": "/static/icons/cogni-pwa-512.jpg", "sizes": "512x512", "type": "image/jpeg", "purpose": "any maskable"},
        ],
    }


def app_status(settings: Settings, vault: Vault, index: Index, host_header: str | None, server_address: tuple | None = None) -> dict:
    local_url = _request_url(host_header, server_address)
    bind_host = _server_bind_host(server_address)
    local_only = bind_host in {"127.0.0.1", "localhost", "::1"}
    port = server_address[1] if server_address else (urlparse(local_url).port or 8765)
    selected = select_public_service_url(settings, port=port)
    phone_url = selected["url"] if selected["cross_device"] else None
    index_health = index.health()
    validation = validate_vault_path(str(vault.root))
    return {
        "service": {
            "name": "Cogni Life OS",
            "status": "online",
            "mode": selected["mode"] if phone_url else "this-device",
            "mode_label": selected["mode_label"] if phone_url else ACCESS_MODE_LABELS["this-device"],
            "access_mode": settings.access_mode,
            "bind_host": bind_host,
            "configured_bind_host": settings.bind_host,
            "configured_port": settings.port,
            "local_url": local_url,
            "reachable_url": phone_url,
            "phone_url": phone_url,
            "public_base_url": settings.public_base_url,
            "selection_source": selected["source"],
            "configured_for_running_service": selected["configured_for_running_service"],
            "lan_ip": selected["lan_ip"],
            "tailscale": selected["tailscale"],
            "loopback_only": local_only,
            "phone_warning": REMOTE_NOT_CONFIGURED_MESSAGE if not phone_url else None,
            "warning": REMOTE_NOT_CONFIGURED_MESSAGE if not phone_url else ("Tailscale/private remote access selected. Service-token authentication is still required." if selected["mode"] == "tailscale" else LAN_WARNING),
        },
        "model": {
            "name": settings.model_name,
            "endpoint": settings.model_base_url,
            "endpoint_status": "configured",
            "live_multimodal": False,
        },
        "vault": {
            "status": "ready" if validation["valid"] else "invalid",
            "path": str(vault.root),
            "readable": validation["readable"],
            "writable": validation["writable"],
            "resembles_markdown_vault": validation["resembles_markdown_vault"],
            "errors": validation["errors"],
            "icloud": validation["icloud"],
            "icloud_warning": validation["icloud_warning"],
        },
        "index": {**index_health, "last_successful_index_time": index_health.get("checked")},
        "safe_operations": {"status": "confirmation required for proposed writes", "quarantine": "enabled"},
        "features": {
            "voice_notes": True,
            "video": False,
            "remote_access": bool(phone_url),
            "live_model_chat": True,
            "file_upload": True,
            "offline_shell": True,
        },
        "voice": voice_status(),
    }


def voice_status() -> dict:
    whisper = shutil.which("whisper-cli")
    stt_ready = bool(whisper and WHISPER_MODEL.exists())
    return {
        "stt": {
            "provider": "whisper-cpp",
            "status": "ready" if stt_ready else "unavailable",
            "engine": whisper,
            "model": str(WHISPER_MODEL),
            "cloud": False,
            "error": None if stt_ready else ("whisper-cli is not installed" if not whisper else f"missing model: {WHISPER_MODEL}"),
        },
        "tts": {
            "provider": "browser speechSynthesis",
            "status": "browser_fallback",
            "cloud": False,
            "local_engine": None,
            "note": "Playback uses the browser/platform voice; Cogni-Brain does not generate audio.",
        },
    }


def transcribe_audio(payload: dict, settings: Settings) -> dict:
    raw = base64.b64decode(payload["data_base64"], validate=True)
    if len(raw) > settings.max_upload_bytes:
        raise ValueError("upload limit exceeded")
    result = extract(raw, payload.get("filename", "voice.wav"))
    data = result.to_dict()
    data["transcript"] = result.extracted_text
    data["preserved"] = False
    data["cloud"] = False
    return data


def chat_turn(settings: Settings, index: Index, payload: dict) -> dict:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("message is required")
    sources = index.search(message)
    context = "\n".join(f"[{i + 1}] {item['title']} ({item['path']})" for i, item in enumerate(sources[:5]))
    messages = [
        {
            "role": "system",
            "content": "You are Cogni-Brain for Cogni Life OS. Answer conversationally. Use only supplied vault context for personal facts. Do not fabricate citations. Keep citations in text when useful.",
        },
        {"role": "user", "content": f"Vault context:\n{context or 'No matching vault sources.'}\n\nUser message:\n{message}"},
    ]
    try:
        raw = chat(settings, messages, max_tokens=700)
        reply = raw.get("choices", [{}])[0].get("message", {}).get("content") or ""
        return {"status": "completed", "reply": reply.strip() or "Cogni-Brain returned an empty reply.", "sources": sources, "model": settings.model_name, "input": payload.get("input", "text")}
    except Exception as exc:
        fallback = "Cogni-Brain is not reachable from this local service. I found vault sources you can inspect below." if sources else "Cogni-Brain is not reachable from this local service, and I found no matching vault sources."
        return {"status": "unavailable", "reply": fallback, "sources": sources, "model": settings.model_name, "detail": f"{type(exc).__name__}: {exc}", "input": payload.get("input", "text")}


def read_static(relative: str) -> tuple[bytes, str]:
    safe = relative.lstrip("/").replace("\\", "/")
    if ".." in safe.split("/"):
        raise FileNotFoundError(relative)
    path = STATIC_ROOT / safe
    if not path.is_file():
        raise FileNotFoundError(relative)
    suffix = path.suffix.lower()
    content_type = {
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".ico": "image/x-icon",
        ".png": "image/png",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")
    return path.read_bytes(), content_type


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


def validate_public_base_url(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https:// and include a host.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("URL must not include credentials, query strings, or fragments.")
    hostname = parsed.hostname or ""
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Localhost cannot be used as a cross-device URL.")
    return raw


def _safe_public_url(value: str) -> str | None:
    try:
        return validate_public_base_url(value) or None
    except ValueError:
        return None


def _is_private_lan_ip(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)


def detect_lan_ip() -> str | None:
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    try:
        host = socket.gethostname()
        candidates.extend(socket.gethostbyname_ex(host)[2])
    except OSError:
        pass
    for candidate in candidates:
        if candidate not in {"127.0.0.1", "0.0.0.0"} and _is_private_lan_ip(candidate):
            return candidate
    return None


def tailscale_status() -> dict:
    if not shutil.which("tailscale"):
        return {"available": False, "connected": False}
    try:
        proc = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=2)
    except Exception as exc:
        return {"available": True, "connected": False, "error": str(exc)}
    if proc.returncode != 0:
        return {"available": True, "connected": False, "error": proc.stderr.strip()}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"available": True, "connected": False, "error": str(exc)}
    return parse_tailscale_status(data)


def parse_tailscale_status(data: dict) -> dict:
    self_info = data.get("Self") or {}
    ips = [ip for ip in self_info.get("TailscaleIPs", []) if "." in str(ip)]
    dns_name = str(self_info.get("DNSName") or "").strip(".")
    hostname = str(self_info.get("HostName") or self_info.get("ComputedName") or "").strip()
    https_url = _safe_public_url(data.get("MagicDNSSuffix") or "")
    if not https_url and dns_name:
        https_url = f"https://{dns_name}"
    return {
        "available": True,
        "connected": bool(self_info and not data.get("BackendState") in {"Stopped", "NoState"}),
        "ipv4": ips[0] if ips else None,
        "hostname": hostname,
        "dns_name": dns_name,
        "https_url": https_url,
        "funnel_enabled": bool(self_info.get("Funnel") or data.get("Funnel")),
    }


def select_public_service_url(settings: Settings, *, port: int | None = None, lan_ip: str | None = None, tailscale: dict | None = None) -> dict:
    service_port = port or settings.port
    lan = lan_ip if lan_ip is not None else detect_lan_ip()
    ts = tailscale if tailscale is not None else tailscale_status()
    configured = _safe_public_url(settings.public_base_url)
    ts_https = _safe_public_url(str(ts.get("https_url") or ""))
    ts_ip = ts.get("ipv4")
    if configured:
        source, url, mode = "configured", configured, (settings.access_mode if settings.access_mode in {"lan", "tailscale", "custom"} else "custom")
    elif settings.access_mode == "this-device":
        source, url, mode = "localhost", None, "this-device"
    elif settings.access_mode == "custom":
        source, url, mode = "localhost", None, "custom"
    elif settings.access_mode == "lan":
        source, url, mode = ("lan", f"http://{lan}:{service_port}", "lan") if lan else ("localhost", None, "lan")
    elif ts_https:
        source, url, mode = "tailscale_https", ts_https, "tailscale"
    elif ts_ip:
        source, url, mode = "tailscale_ip", f"http://{ts_ip}:{service_port}", "tailscale"
    elif lan:
        source, url, mode = "lan", f"http://{lan}:{service_port}", "lan"
    else:
        source, url, mode = "localhost", None, "this-device"
    bind_all = settings.bind_host == "0.0.0.0"
    configured_for_running_service = bool(
        configured
        or (mode == "lan" and bind_all)
        or (mode == "tailscale" and (bind_all or settings.bind_host == str(ts_ip) or source == "tailscale_https"))
    )
    return {
        "mode": mode,
        "mode_label": ACCESS_MODE_LABELS.get(mode, mode),
        "url": url,
        "source": source,
        "cross_device": bool(url and source != "localhost"),
        "configured_for_running_service": configured_for_running_service,
        "tailscale": ts,
        "lan_ip": lan,
    }


def _server_bind_host(server_address: tuple | None) -> str:
    if not server_address:
        return "127.0.0.1"
    host = server_address[0]
    return "127.0.0.1" if host in {"", "localhost"} else str(host)


def _is_icloud_path(path: Path) -> bool:
    marker = str(path).lower()
    return any(part in marker for part in ("icloud", "mobile documents", "com~apple~clouddocs"))


def validate_vault_path(path_value: str) -> dict:
    errors: list[str] = []
    if not str(path_value or "").strip():
        return {"valid": False, "path": "", "errors": ["Vault path is required."]}
    expanded = Path(path_value).expanduser()
    if not expanded.is_absolute():
        errors.append("Vault path must be absolute.")
        resolved = expanded
    else:
        resolved = expanded.resolve()
    if not resolved.exists():
        errors.append("Folder does not exist.")
    elif not resolved.is_dir():
        errors.append("Path is not a folder.")
    readable = resolved.is_dir() and os.access(resolved, os.R_OK)
    writable = False
    if resolved.exists() and resolved.is_dir():
        if not readable:
            errors.append("Folder is not readable.")
        try:
            with tempfile.NamedTemporaryFile(prefix=".cogni-write-test-", dir=resolved, delete=True) as handle:
                handle.write(b"ok")
                handle.flush()
            writable = True
        except OSError:
            errors.append("Folder is not writable.")
    markdown_count = 0
    resembles = False
    if resolved.exists() and resolved.is_dir() and readable:
        markdown_count = sum(1 for _ in resolved.rglob("*.md"))
        known_dirs = {"00-system", "10-sources", "30-concepts", ".obsidian"}
        resembles = markdown_count > 0 or any((resolved / item).exists() for item in known_dirs)
        if not resembles:
            errors.append("Folder does not appear to contain Markdown notes or a known vault structure.")
    icloud = _is_icloud_path(resolved)
    return {
        "valid": not errors,
        "path": str(resolved),
        "errors": errors,
        "readable": readable,
        "writable": writable,
        "markdown_count": markdown_count,
        "resembles_markdown_vault": resembles,
        "icloud": icloud,
        "icloud_warning": ICLOUD_WARNING if icloud else None,
    }


def save_vault_config(settings: Settings, index: Index, current_vault: Vault, path_value: str, *, confirm_switch: bool = False) -> tuple[Vault, dict]:
    validation = validate_vault_path(path_value)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    requested = Path(validation["path"])
    indexed = index.health().get("note_count", 0)
    if requested != current_vault.root.resolve() and indexed and not confirm_switch:
        raise PermissionError("Confirm before switching away from an indexed vault.")
    before_files = {path.relative_to(requested) for path in requested.rglob("*") if path.is_file()}
    persist_vault_path(requested, settings.local_config_path)
    new_vault = Vault(requested)
    count = index.rebuild(new_vault)
    after_files = {path.relative_to(requested) for path in requested.rglob("*") if path.is_file()}
    return new_vault, {
        "status": "saved",
        "path": str(requested),
        "index_count": count,
        "moved_source_files": False,
        "deleted_source_files": not before_files.issubset(after_files),
        "source_files_modified": False,
        "icloud": validation["icloud"],
        "icloud_warning": validation["icloud_warning"],
    }


def validate_access_config(mode: str, public_base_url: str) -> dict:
    mode = mode if mode in ACCESS_MODE_LABELS else "this-device"
    try:
        normalized = validate_public_base_url(public_base_url) if public_base_url else ""
    except ValueError as exc:
        return {"valid": False, "mode": mode, "public_base_url": "", "error": str(exc)}
    if mode == "custom" and not normalized:
        return {"valid": False, "mode": mode, "public_base_url": "", "error": "Custom URL mode requires a public base URL."}
    return {"valid": True, "mode": mode, "mode_label": ACCESS_MODE_LABELS[mode], "public_base_url": normalized}


def save_access_config(settings: Settings, mode: str, public_base_url: str) -> dict:
    validation = validate_access_config(mode, public_base_url)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    persist_local_config(
        {
            "COGNI_ACCESS_MODE": validation["mode"],
            "COGNI_PUBLIC_BASE_URL": validation["public_base_url"],
        },
        settings.local_config_path,
    )
    return {**validation, "restart_required": False, "bind_host": settings.bind_host, "port": settings.port}


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
            if parsed.path.startswith("/static/"):
                try:
                    body, content_type = read_static(parsed.path[len("/static/") :])
                except FileNotFoundError:
                    self._json(404, {"error": "not_found"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", content_type)
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
            nonlocal vault
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/") and not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                if parsed.path == "/api/vault/validate":
                    payload = self._read_json()
                    self._json(200, validate_vault_path(str(payload.get("path", ""))))
                    return
                if parsed.path == "/api/access/validate":
                    payload = self._read_json()
                    result = validate_access_config(str(payload.get("mode", "")), str(payload.get("public_base_url", "")))
                    self._json(200 if result["valid"] else 400, result)
                    return
                if parsed.path == "/api/access/save":
                    payload = self._read_json()
                    try:
                        result = save_access_config(settings, str(payload.get("mode", "")), str(payload.get("public_base_url", "")))
                    except ValueError as exc:
                        self._json(400, {"valid": False, "error": "invalid_access_config", "detail": str(exc)})
                        return
                    self._json(200, result)
                    return
                if parsed.path == "/api/vault/save":
                    payload = self._read_json()
                    try:
                        vault, result = save_vault_config(settings, index, vault, str(payload.get("path", "")), confirm_switch=bool(payload.get("confirm_switch")))
                    except PermissionError as exc:
                        self._json(409, {"error": "confirmation_required", "detail": str(exc)})
                        return
                    except ValueError as exc:
                        self._json(400, {"error": "invalid_vault_path", "detail": str(exc)})
                        return
                    self._json(200, result)
                    return
                if parsed.path == "/api/index/rebuild":
                    count = index.rebuild(vault)
                    self._json(200, {"status": "rebuilt", "count": count, "source_files_modified": False})
                    return
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
                if parsed.path == "/api/transcribe":
                    payload = self._read_json()
                    self._json(200, transcribe_audio(payload, settings))
                    return
                if parsed.path == "/api/chat":
                    payload = self._read_json()
                    self._json(200, chat_turn(settings, index, payload))
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
    if host not in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
        raise ValueError("service may only bind to loopback addresses or 0.0.0.0 for explicit LAN access")
    server = ThreadingHTTPServer((host, port), make_handler(settings))
    print(f"Cogni Life OS listening on http://{host}:{port}")
    if host == "0.0.0.0":
        lan_ip = detect_lan_ip()
        print(f"LAN URL: {'http://' + lan_ip + ':' + str(port) if lan_ip else 'unavailable'}")
        print(LAN_WARNING)
    print("Service token: [REDACTED]")
    server.serve_forever()
