from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .planner import build_campaign


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Adtech Campaign Architect</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #10131a;
      --muted: #646b78;
      --quiet: #8b93a3;
      --line: #dfe3ea;
      --panel: #ffffff;
      --soft: #f7f8fb;
      --blue: #2457d6;
      --teal: #087f6f;
      --green: #0b7a43;
      --amber: #9a5a00;
      --red: #c72c41;
      --shadow: 0 12px 34px rgba(23, 32, 54, 0.08);
      --radius: 8px;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      padding-bottom: 88px;
      background: linear-gradient(180deg, #fafbfe 0%, #f2f5f9 100%);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, select, textarea { font: inherit; }
    button { cursor: pointer; }
    p { margin: 0; color: var(--muted); line-height: 1.45; }
    h1, h2, h3 { margin: 0; letter-spacing: 0; }

    .studio {
      width: min(100%, 1280px);
      margin: 0 auto;
      padding: 18px 24px 28px;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 900;
      font-size: 17px;
    }
    .brand-mark {
      display: grid;
      place-items: center;
      width: 32px;
      height: 32px;
      border-radius: var(--radius);
      background: var(--ink);
      color: #fff;
      font-size: 17px;
    }
    .status-chip, .pill, .check {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }
    .status-chip.ready { color: var(--green); border-color: #b9e4ce; background: #effaf4; }
    .status-chip.working { color: var(--blue); border-color: #c9d6ff; background: #f0f4ff; }
    .status-chip.warn { color: var(--amber); border-color: #f0d5a3; background: #fff8eb; }
    .pill.blue { color: var(--blue); background: #eef3ff; border-color: #ccd9ff; }
    .pill.green { color: var(--green); background: #effaf4; border-color: #b9e4ce; }
    .pill.amber { color: var(--amber); background: #fff8eb; border-color: #f0d5a3; }

    .launchpad {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, 1fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      box-shadow: var(--shadow);
    }
    .input-panel, .brain-panel, .config-panel, .creative-panel { padding: 20px; }
    .panel-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    .panel-title { font-size: 21px; line-height: 1.15; }
    .panel-subtitle { max-width: 640px; margin-top: 6px; font-size: 13px; }
    textarea {
      width: 100%;
      min-height: 142px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 16px;
      background: #fff;
      color: var(--ink);
      font-size: 16px;
      line-height: 1.45;
      outline: none;
    }
    textarea:focus, input:focus, select:focus {
      border-color: rgba(36, 87, 214, 0.74);
      box-shadow: 0 0 0 4px rgba(36, 87, 214, 0.12);
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    label {
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 850;
      text-transform: uppercase;
    }
    input, select {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0 12px;
      background: #fff;
      color: var(--ink);
      outline: none;
    }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      margin-top: 14px;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0 16px;
      background: #fff;
      color: var(--ink);
      font-weight: 850;
    }
    .button:disabled {
      cursor: wait;
      opacity: 0.68;
    }
    .button.primary {
      min-width: 216px;
      border-color: var(--blue);
      background: var(--blue);
      color: #fff;
      box-shadow: 0 14px 28px rgba(36, 87, 214, 0.22);
    }
    .button.dark { background: var(--ink); color: #fff; border-color: var(--ink); }
    .icon { font-size: 15px; line-height: 1; }
    .examples {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .example {
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      padding: 7px 11px;
      font-size: 12px;
      font-weight: 800;
      line-height: 1.2;
      text-align: left;
    }
    .example.active { color: var(--blue); border-color: #c9d6ff; background: #f0f4ff; }

    .brain-map {
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 54px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      min-height: 156px;
      padding: 4px 0;
    }
    .node-card {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      padding: 14px;
    }
    .node-label {
      color: var(--quiet);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .node-title {
      margin-top: 7px;
      font-size: 18px;
      font-weight: 900;
      line-height: 1.18;
      overflow-wrap: anywhere;
    }
    .node-meta { margin-top: 8px; font-size: 13px; }
    .connector {
      position: relative;
      height: 4px;
      overflow: hidden;
      border-radius: 999px;
      background: #d9e1ef;
    }
    .connector::after {
      content: "";
      position: absolute;
      inset: 0;
      width: 42%;
      border-radius: inherit;
      background: linear-gradient(90deg, transparent, var(--blue), transparent);
      animation: think 1.25s linear infinite;
    }
    @keyframes think {
      from { transform: translateX(-120%); }
      to { transform: translateX(260%); }
    }
    .persona-strip {
      display: grid;
      grid-template-columns: 46px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 14px;
      background: var(--soft);
    }
    .avatar {
      display: grid;
      place-items: center;
      width: 46px;
      height: 46px;
      border-radius: 50%;
      background: linear-gradient(135deg, #eaf2ff, #e9fbf5);
      color: var(--blue);
      font-size: 17px;
      font-weight: 950;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(380px, 0.92fr) minmax(0, 1.08fr);
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }
    .intent-card, .guardrail, .blueprint, .variant-preview {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      padding: 16px;
    }
    .intent-card { margin-bottom: 14px; }
    .intent-top, .variant-tabs, .guardrail-top, .ad-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .tiny-button {
      display: inline-grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--soft);
      color: var(--ink);
      font-weight: 900;
    }
    [contenteditable="true"] {
      outline: none;
      border-radius: 5px;
    }
    [contenteditable="true"]:focus {
      box-shadow: 0 0 0 3px rgba(36, 87, 214, 0.12);
      background: #f8fbff;
    }
    .field-stack { display: grid; gap: 12px; }
    .range-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
    }
    input[type="range"] {
      min-height: auto;
      padding: 0;
      accent-color: var(--blue);
    }
    .guardrail { margin-top: 14px; }
    .guardrail-message {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: var(--radius);
      background: #effaf4;
      color: var(--green);
      font-weight: 850;
      font-size: 13px;
    }
    .guardrail-message.warn { background: #fff8eb; color: var(--amber); }
    .guardrail-message.danger { background: #fff1f3; color: var(--red); }
    .bar-chart {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .chart-row {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr) 64px;
      gap: 10px;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }
    .chart-track {
      height: 18px;
      overflow: hidden;
      border-radius: 999px;
      background: #edf1f6;
    }
    .chart-fill {
      display: block;
      width: var(--w, 1%);
      height: 100%;
      border-radius: inherit;
      background: var(--teal);
    }
    .chart-fill.cpa { background: var(--blue); }
    .line-list {
      display: grid;
      gap: 1px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--line);
    }
    .line-item {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 12px 13px;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
    }
    .line-item strong { color: var(--ink); }
    .line-item span { text-align: right; overflow-wrap: anywhere; }
    .chip {
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      min-height: 25px;
      margin: 3px 4px 0 0;
      padding: 3px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }
    .section-gap { margin-top: 14px; }
    .section-title {
      margin-bottom: 10px;
      font-size: 16px;
      line-height: 1.2;
    }
    .candidate-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .candidate {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--soft);
      padding: 12px;
    }
    .candidate strong { display: block; line-height: 1.2; }
    .score {
      color: var(--blue);
      font-size: 24px;
      font-weight: 950;
      line-height: 1;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .detail-card {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      overflow: hidden;
    }
    .detail-card h4 {
      margin: 0;
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      background: var(--soft);
      color: var(--ink);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .detail-rows {
      display: grid;
      gap: 1px;
      background: var(--line);
    }
    .detail-row {
      display: grid;
      grid-template-columns: minmax(120px, 0.36fr) minmax(0, 1fr);
      gap: 12px;
      padding: 10px 12px;
      background: #fff;
      font-size: 13px;
    }
    .detail-key {
      color: var(--quiet);
      font-weight: 900;
      text-transform: uppercase;
    }
    .detail-value {
      min-width: 0;
      color: var(--ink);
      overflow-wrap: anywhere;
    }
    .nested-rows {
      display: grid;
      gap: 7px;
    }
    .nested-row {
      display: grid;
      grid-template-columns: minmax(96px, 0.34fr) minmax(0, 1fr);
      gap: 10px;
    }
    .nested-key {
      color: var(--muted);
      font-weight: 850;
    }
    .empty-value {
      color: var(--quiet);
      font-style: italic;
    }
    .variant-tabs {
      flex-wrap: wrap;
      justify-content: flex-start;
      margin-bottom: 14px;
    }
    .tab {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #fff;
      color: var(--muted);
      padding: 0 12px;
      font-weight: 850;
      font-size: 13px;
    }
    .tab.active {
      border-color: var(--ink);
      background: var(--ink);
      color: #fff;
    }
    .ad-mock {
      overflow: hidden;
      border: 1px solid #cad1dc;
      border-radius: var(--radius);
      background: #fff;
    }
    .ad-head {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #f6f8fb;
    }
    .publisher-logo {
      display: inline-grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: var(--radius);
      background: var(--teal);
      color: #fff;
      font-weight: 950;
    }
    .ad-body { padding: 18px; }
    .ad-label {
      color: var(--quiet);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .ad-title {
      margin-top: 8px;
      font-size: clamp(24px, 3vw, 38px);
      line-height: 1.08;
      font-weight: 950;
    }
    .ad-copy {
      margin-top: 12px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.45;
    }
    .cta {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      margin-top: 16px;
      border-radius: var(--radius);
      padding: 0 16px;
      background: var(--blue);
      color: #fff;
      font-weight: 900;
    }
    .why {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--soft);
    }
    .why summary {
      cursor: pointer;
      padding: 12px 14px;
      color: var(--ink);
      font-weight: 900;
    }
    .why p { padding: 0 14px 14px; }
    .empty {
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      padding: 16px;
      background: #fff;
      color: var(--muted);
    }

    .launchbar {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 10;
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(14px);
      box-shadow: 0 -12px 32px rgba(23, 32, 54, 0.1);
    }
    .launchbar-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      width: min(100%, 1320px);
      min-height: 74px;
      margin: 0 auto;
      padding: 10px 28px;
    }
    .checklist {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .check::before {
      content: "";
      width: 8px;
      height: 8px;
      margin-right: 7px;
      border-radius: 50%;
      background: var(--green);
    }

    @media (max-width: 1040px) {
      .launchpad, .workspace { grid-template-columns: 1fr; }
      .brain-map { grid-template-columns: 1fr; }
      .connector { height: 34px; width: 4px; margin: 0 auto; }
      .connector::after { width: 100%; height: 42%; animation-name: thinkVertical; }
      @keyframes thinkVertical {
        from { transform: translateY(-120%); }
        to { transform: translateY(260%); }
      }
    }
    @media (max-width: 720px) {
      body { padding-bottom: 132px; }
      .studio { padding: 16px; }
      .topbar, .panel-head, .button-row, .launchbar-inner { align-items: stretch; flex-direction: column; }
      .controls, .candidate-grid, .detail-grid { grid-template-columns: 1fr; }
      .input-panel, .brain-panel, .config-panel, .creative-panel { padding: 16px; }
      .button.primary, .button.dark { width: 100%; }
      .line-item, .chart-row { grid-template-columns: 1fr; }
      .line-item { display: grid; }
      .line-item span { text-align: left; }
    }
  </style>
</head>
<body>
  <main class="studio">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">A</span> Adtech Campaign Architect</div>
      <span class="status-chip ready" id="statusChip">Ready</span>
    </header>

    <section class="launchpad" aria-label="Launchpad">
      <div class="panel input-panel">
        <div class="panel-head">
          <div>
            <h1 class="panel-title">Launchpad</h1>
            <p class="panel-subtitle">Tell us what you sell. The planner turns messy input into a reviewable campaign.</p>
          </div>
          <span class="pill blue">Input canvas</span>
        </div>
        <textarea id="description" placeholder="Tell us what you sell, who loves it, or just drop your website link. Don't worry about making it sound professional-we'll handle that.">We sell premium dog food for senior dogs, targeting owners who care about joint health.</textarea>
        <div class="controls">
          <label>Target publisher
            <select id="publisherPreference">
              <option value="">Let AI choose</option>
              <option>PetWell Checkout Network</option>
              <option>FitCart Post-Purchase</option>
              <option>HomeGoods Newsletter</option>
            </select>
          </label>
          <label>Strict daily budget
            <input id="strictBudget" type="number" min="0" step="25" placeholder="Optional, e.g. 50" />
          </label>
        </div>
        <div class="examples" id="quickPrompts"></div>
        <div class="button-row">
          <button class="button" id="reset" type="button">Reset</button>
          <button class="button primary" id="run" type="button">Generate Campaign</button>
        </div>
      </div>

      <aside class="panel brain-panel" aria-label="Live match map">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">Live Match Map</h2>
            <p class="panel-subtitle" id="brainSubcopy">The brain will map product, publisher, persona, and economics here.</p>
          </div>
          <span class="pill green" id="confidencePill">Awaiting brief</span>
        </div>
        <div class="brain-map">
          <div class="node-card">
            <div class="node-label">Advertiser product</div>
            <div class="node-title" id="productNode">Senior dog food</div>
            <p class="node-meta" id="intentNode">Premium pet nutrition for joint-health focused owners.</p>
          </div>
          <div class="connector" aria-hidden="true"></div>
          <div class="node-card">
            <div class="node-label">Best-fit publisher</div>
            <div class="node-title" id="publisherNode">Not generated yet</div>
            <p class="node-meta" id="publisherMeta">Publisher AOV, placement context, and fit score will appear here.</p>
          </div>
        </div>
        <div class="persona-strip">
          <div class="avatar" id="personaAvatar">?</div>
          <div>
            <div class="node-label">Target shopper</div>
            <div class="node-title" id="personaNode">Persona pending</div>
            <p class="node-meta" id="personaMeta">Persona psychology will load after matching.</p>
          </div>
        </div>
      </aside>
    </section>

    <section class="workspace" id="workspace" aria-label="Campaign workspace">
      <section class="panel config-panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">Configuration & Financial Guardrails</h2>
            <p class="panel-subtitle">Editable campaign strategy without touching raw JSON.</p>
          </div>
        </div>

        <article class="intent-card">
          <div class="intent-top">
            <div>
              <div class="node-label">Decoded value proposition</div>
              <h3 id="intentSummary" contenteditable="true">Generate a campaign to see the decoded intent.</h3>
            </div>
            <button class="tiny-button" type="button" title="Edit decoded intent">Edit</button>
          </div>
        </article>

        <div class="field-stack">
          <label>Bid strategy
            <div class="range-row">
              <input id="bidSlider" type="range" min="1" max="60" step="0.5" value="18" />
              <strong id="bidValue">$18 CPM</strong>
            </div>
          </label>
          <label>Daily spend
            <input id="dailyBudget" type="number" min="1" step="25" value="250" />
          </label>
        </div>

        <article class="guardrail">
          <div class="guardrail-top">
            <h3 class="section-title">Profitability Guardrail</h3>
            <span class="pill green" id="mathStatus">Safe zone</span>
          </div>
          <div class="bar-chart" id="aovChart"></div>
          <div class="guardrail-message" id="guardrailMessage">Generate a campaign to compare publisher AOV against target CPA.</div>
        </article>

        <div class="section-gap">
          <h3 class="section-title">Targeting & Measurement</h3>
          <div class="line-list" id="configRows"></div>
        </div>
        <div class="section-gap">
          <h3 class="section-title">Ranked Publishers</h3>
          <div class="candidate-grid" id="publisherCandidates"></div>
        </div>
        <div class="section-gap">
          <h3 class="section-title">Selected Details</h3>
          <div class="detail-grid">
            <article class="detail-card">
              <h4>Publisher</h4>
              <div class="detail-rows" id="publisherDetails"></div>
            </article>
            <article class="detail-card">
              <h4>Target Audience</h4>
              <div class="detail-rows" id="personaDetails"></div>
            </article>
          </div>
        </div>
      </section>

      <section class="panel creative-panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">Creative Sandbox</h2>
            <p class="panel-subtitle">Review the generated copy in a native placement mockup. Text is directly editable.</p>
          </div>
          <span class="pill amber" id="variantCount">0 variants</span>
        </div>
        <div class="variant-tabs" id="variantTabs" role="tablist" aria-label="Creative variants"></div>
        <div class="variant-preview" id="creativePreview">
          <div class="empty">Generate a campaign to render the ad variants.</div>
        </div>
        <div class="section-gap">
          <h3 class="section-title">Psychological Blueprint</h3>
          <div class="line-list" id="blueprintRows"></div>
        </div>
        <div class="section-gap">
          <h3 class="section-title">Excluded Publishers</h3>
          <div id="exclusions" class="candidate-grid"></div>
        </div>
      </section>
    </section>
  </main>

  <footer class="launchbar" aria-label="Launch actions">
    <div class="launchbar-inner">
      <div class="checklist">
        <span class="check" id="targetCheck">Target pending</span>
        <span class="check" id="budgetCheck">Budget pending</span>
        <span class="check" id="adsCheck">Ads pending</span>
      </div>
      <button class="button dark" id="launchButton" type="button">Launch Campaign</button>
    </div>
  </footer>

  <script>
    const description = document.querySelector("#description");
    const publisherPreference = document.querySelector("#publisherPreference");
    const strictBudget = document.querySelector("#strictBudget");
    const quickPrompts = document.querySelector("#quickPrompts");
    const statusChip = document.querySelector("#statusChip");
    const productNode = document.querySelector("#productNode");
    const intentNode = document.querySelector("#intentNode");
    const publisherNode = document.querySelector("#publisherNode");
    const publisherMeta = document.querySelector("#publisherMeta");
    const personaNode = document.querySelector("#personaNode");
    const personaMeta = document.querySelector("#personaMeta");
    const personaAvatar = document.querySelector("#personaAvatar");
    const confidencePill = document.querySelector("#confidencePill");
    const brainSubcopy = document.querySelector("#brainSubcopy");
    const intentSummary = document.querySelector("#intentSummary");
    const bidSlider = document.querySelector("#bidSlider");
    const bidValue = document.querySelector("#bidValue");
    const dailyBudget = document.querySelector("#dailyBudget");
    const aovChart = document.querySelector("#aovChart");
    const guardrailMessage = document.querySelector("#guardrailMessage");
    const mathStatus = document.querySelector("#mathStatus");
    const configRows = document.querySelector("#configRows");
    const publisherCandidates = document.querySelector("#publisherCandidates");
    const publisherDetails = document.querySelector("#publisherDetails");
    const personaDetails = document.querySelector("#personaDetails");
    const variantTabs = document.querySelector("#variantTabs");
    const creativePreview = document.querySelector("#creativePreview");
    const blueprintRows = document.querySelector("#blueprintRows");
    const exclusions = document.querySelector("#exclusions");
    const variantCount = document.querySelector("#variantCount");
    const runButton = document.querySelector("#run");
    const resetButton = document.querySelector("#reset");
    let currentData = null;
    let activeVariant = 0;
    let loadingTimer = null;
    let loadingStartedAt = 0;

    const defaultBrief = description.value;
    const examples = [
      "We sell premium dog food for senior dogs, targeting owners who care about joint health.",
      "A meditation app for busy parents who want 5-minute resets and better sleep.",
      "Sustainable bamboo cookware for eco-conscious home cooks.",
      "A sustainable activewear brand for women. Made from recycled ocean plastic."
    ];

    quickPrompts.innerHTML = examples.map((text, index) => `<button class="example ${index === 0 ? "active" : ""}" type="button" data-index="${index}">${escapeHtml(text)}</button>`).join("");
    quickPrompts.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      description.value = examples[Number(button.dataset.index)];
      document.querySelectorAll(".example").forEach((item) => item.classList.toggle("active", item === button));
      run();
    });
    runButton.addEventListener("click", run);
    resetButton.addEventListener("click", () => {
      description.value = defaultBrief;
      publisherPreference.value = "";
      strictBudget.value = "";
      document.querySelectorAll(".example").forEach((item, index) => item.classList.toggle("active", index === 0));
      run();
    });
    document.querySelector("#launchButton").addEventListener("click", () => {
      if (!currentData) return;
      statusChip.textContent = "Campaign queued";
      statusChip.className = "status-chip ready";
    });
    bidSlider.addEventListener("input", updateFinancials);
    dailyBudget.addEventListener("input", updateFinancials);

    run();

    async function run() {
      if (runButton.disabled) return;
      setLoading();
      const brief = withOptionalInputs(description.value);
      try {
        const response = await fetch("/api/campaign", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ description: brief })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        render(payload);
      } catch (error) {
        statusChip.textContent = "Generation failed";
        statusChip.className = "status-chip warn";
        creativePreview.innerHTML = `<div class="empty">The planner did not return a campaign: ${escapeHtml(error.message)}</div>`;
      } finally {
        stopLoading();
      }
    }

    function withOptionalInputs(text) {
      const additions = [];
      if (publisherPreference.value) additions.push(`Preferred publisher: ${publisherPreference.value}.`);
      if (strictBudget.value) additions.push(`Strict daily budget: $${strictBudget.value}.`);
      return [text.trim(), ...additions].filter(Boolean).join("\\n");
    }

    function setLoading() {
      loadingStartedAt = Date.now();
      runButton.disabled = true;
      resetButton.disabled = true;
      runButton.textContent = "Generating...";
      statusChip.textContent = "Matching 0s";
      statusChip.className = "status-chip working";
      brainSubcopy.textContent = "Scoring publisher fit, persona psychology, bid math, and creative angles.";
      publisherNode.textContent = "Scoring candidates";
      publisherMeta.textContent = "Looking for AOV, placement, and audience fit.";
      personaNode.textContent = "Building persona";
      personaMeta.textContent = "Extracting motivations and likely friction points.";
      creativePreview.innerHTML = '<div class="empty">Writing persona-tuned ad variants...</div>';
      clearInterval(loadingTimer);
      loadingTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - loadingStartedAt) / 1000);
        statusChip.textContent = `Matching ${elapsed}s`;
      }, 1000);
    }

    function stopLoading() {
      clearInterval(loadingTimer);
      loadingTimer = null;
      runButton.disabled = false;
      resetButton.disabled = false;
      runButton.textContent = "Generate Campaign";
    }

    function render(data) {
      currentData = data;
      activeVariant = 0;
      const understanding = data.advertiser_understanding || {};
      const config = data.campaign_config || {};
      const bid = config.bid_strategy || {};
      const topPublisher = selectedPublisher(data) || {};
      const topPersona = selectedPersona(data) || {};
      const blueprint = data.psychological_blueprint || config.psychological_blueprint || {};
      const bidType = (bid.type || "cpm").toUpperCase();
      const bidRange = activeBidRange(bid);
      const startBid = Number(bidRange[0] || 10);

      statusChip.textContent = "Generated";
      statusChip.className = "status-chip ready";
      productNode.textContent = understanding.product || "Product decoded";
      intentNode.textContent = understanding.primary_intent || "Intent ready for review.";
      publisherNode.textContent = topPublisher.name || "No launchable publisher";
      publisherMeta.textContent = topPublisher.name ? `${formatNumber(topPublisher.monthly_impressions)} impressions - ${formatCurrency(topPublisher.avg_order_value_usd)} AOV - ${topPublisher.score} fit` : "Clarify the brief or add better matched supply.";
      personaNode.textContent = topPersona.name || config.target_persona || "No persona selected";
      personaMeta.textContent = topPersona.description || blueprint.friction_point || "Persona reasoning pending.";
      personaAvatar.textContent = initials(topPersona.name || config.target_persona || "?");
      confidencePill.textContent = titleize(understanding.confidence || "medium");
      confidencePill.className = `pill ${understanding.confidence === "low" ? "amber" : "green"}`;
      brainSubcopy.textContent = data.llm_selection?.click_hypothesis || "Publisher, persona, and creative strategy are ready for review.";
      intentSummary.textContent = understanding.primary_intent || config.objective || "Campaign intent";

      bidSlider.min = Math.max(0.5, Math.floor(Number(bidRange[0] || 1) * 0.5));
      bidSlider.max = Math.max(8, Math.ceil(Number(bidRange[1] || 60) * 1.6));
      bidSlider.value = startBid;
      bidValue.textContent = `${formatCurrency(startBid)} ${bidType}`;
      dailyBudget.value = strictBudget.value || config.budget?.daily_starting_budget_usd || Math.round((config.budget?.recommended_test_budget_usd || 3000) / (config.flight?.duration_days || 30));

      configRows.innerHTML = `
        ${lineItem("Objective", config.objective || "Qualified traffic")}
        ${lineItem("Primary publisher", config.target_publisher || topPublisher.name || "not selected")}
        ${lineItem("Creative audiences", creativeAudienceSummary(data, config))}
        ${lineItem("Budget allocation", budgetAllocationSummary(config))}
        ${lineItem("Bid strategy", `${bidType} - ${escapeHtml(bid.explanation || bid.optimization || "Optimize toward qualified engagement")}`)}
        ${lineItem("Targeting rationale", config.targeting_rationale || "not provided")}
        ${lineItem("Signals", chipList([...(understanding.categories || []), ...(understanding.subcategories || []), ...(understanding.positioning || [])]))}
      `;
      publisherCandidates.innerHTML = (data.recommended_publishers || []).length
        ? data.recommended_publishers.map(candidateCard).join("")
        : '<div class="empty">No launchable publisher fit. Clarify the brief or add better matched supply.</div>';
      publisherDetails.innerHTML = detailRows(topPublisher);
      personaDetails.innerHTML = detailRows(topPersona);
      blueprintRows.innerHTML = `
        ${lineItem("Contextual vibe", blueprint.contextual_vibe || "not provided")}
        ${lineItem("Friction point", blueprint.friction_point || "not provided")}
        ${lineItem("Conversion angle", blueprint.angle || "not provided")}
        ${lineItem("Financial reasoning", bid.financial_reasoning || "not provided")}
      `;
      exclusions.innerHTML = (data.excluded_publishers || []).slice(0, 4).map(excludedCard).join("") || '<div class="empty">No exclusions returned.</div>';

      renderVariantTabs(data.creative_variants || []);
      renderCreative();
      updateFinancials();
      document.querySelector("#targetCheck").textContent = topPublisher.name ? "Target locked" : "Target needs review";
      document.querySelector("#adsCheck").textContent = (data.creative_variants || []).length ? "Ads ready" : "Ads pending";
    }

    function renderVariantTabs(variants) {
      variantCount.textContent = `${variants.length} variants`;
      variantTabs.innerHTML = variants.map((variant, index) => `<button class="tab ${index === activeVariant ? "active" : ""}" type="button" data-index="${index}">${escapeHtml(variant.persona_name || variant.variant_type || `Variant ${index + 1}`)}</button>`).join("");
      variantTabs.onclick = (event) => {
        const tab = event.target.closest(".tab");
        if (!tab) return;
        activeVariant = Number(tab.dataset.index);
        renderVariantTabs(currentData.creative_variants || []);
        renderCreative();
      };
    }

    function renderCreative() {
      const variants = currentData?.creative_variants || [];
      const variant = variants[activeVariant];
      const publisher = selectedPublisher(currentData || {}) || {};
      if (!variant) {
        creativePreview.innerHTML = '<div class="empty">No creative variants returned.</div>';
        return;
      }
      creativePreview.innerHTML = `
        <div class="ad-mock">
          <div class="ad-head">
            <div style="display:flex;align-items:center;gap:10px;min-width:0">
              <span class="publisher-logo">${escapeHtml(initials(publisher.name || "Ad"))}</span>
              <div style="min-width:0">
                <strong>${escapeHtml(publisher.name || "Publisher placement")}</strong>
                <p style="font-size:12px">${escapeHtml(publisher.category || "native placement")} sponsored module</p>
              </div>
            </div>
            <span class="pill blue">Sponsored</span>
          </div>
          <div class="ad-body">
            <div class="ad-label">${escapeHtml(variant.variant_type || "Creative variant")} - ${escapeHtml(variant.persona_name || "Target audience")}</div>
            <div class="ad-title" contenteditable="true">${escapeHtml(variant.headline || "Headline")}</div>
            <div class="ad-copy" contenteditable="true">${escapeHtml(variant.body || "Body copy")}</div>
            <div class="cta" contenteditable="true">${escapeHtml(variant.cta || "Learn More")}</div>
          </div>
        </div>
        <div class="line-list" style="margin-top:14px">
          ${lineItem("Target audience", `${escapeHtml(variant.persona_name || "not provided")} - ${escapeHtml(String(variant.persona_fit_score ?? "n/a"))} fit`)}
          ${lineItem("Persona reasoning", chipList(variant.persona_reasoning || []))}
        </div>
        <details class="why">
          <summary>Why this works</summary>
          <p>${escapeHtml(variant.why_this_works || variant.persona_reasoning?.[0] || "This angle is tailored to the selected persona and publisher context.")}</p>
        </details>
      `;
    }

    function updateFinancials() {
      const data = currentData || {};
      const publisher = selectedPublisher(data) || {};
      const config = data.campaign_config || {};
      const bid = config.bid_strategy || {};
      const bidType = (bid.type || "cpm").toUpperCase();
      const selectedBid = Number(bidSlider.value || 0);
      const targetCpa = Number(bid.target_cpa_guardrail_usd || publisher.avg_order_value_usd * 0.32 || 20);
      const aov = Number(publisher.avg_order_value_usd || 75);
      const max = Math.max(aov, targetCpa, selectedBid, 1);
      const cpaPct = Math.max(2, Math.min(100, (targetCpa / max) * 100));
      const aovPct = Math.max(2, Math.min(100, (aov / max) * 100));
      const cpaRatio = targetCpa / Math.max(aov, 1);
      const bidRange = activeBidRange(bid);
      const low = Number(bidRange[0] || 1);
      const high = Number(bidRange[1] || 60);

      bidValue.textContent = `${formatCurrency(selectedBid)} ${bidType}`;
      aovChart.innerHTML = `
        <div class="chart-row"><span>Publisher AOV</span><div class="chart-track"><span class="chart-fill" style="--w:${aovPct}%"></span></div><strong>${formatCurrency(aov)}</strong></div>
        <div class="chart-row"><span>Target CPA</span><div class="chart-track"><span class="chart-fill cpa" style="--w:${cpaPct}%"></span></div><strong>${formatCurrency(targetCpa)}</strong></div>
      `;

      let state = "Safe zone";
      let message = `Safe Zone: target CPA ${formatCurrency(targetCpa)} is below publisher AOV ${formatCurrency(aov)}.`;
      let className = "guardrail-message";
      if (selectedBid < low) {
        state = "Bid too low";
        message = `Your ${bidType} is below the suggested range. The ad might not win enough auctions.`;
        className = "guardrail-message warn";
      } else if (selectedBid > high) {
        state = "Bid high";
        message = `Your ${bidType} is above the suggested range. This could compress margins.`;
        className = "guardrail-message warn";
      } else if (cpaRatio > 0.55) {
        state = "Margin risk";
        message = `Target CPA is close to AOV. Review margin before launch.`;
        className = "guardrail-message danger";
      }
      guardrailMessage.textContent = message;
      guardrailMessage.className = className;
      mathStatus.textContent = state;
      mathStatus.className = `pill ${className.includes("danger") || className.includes("warn") ? "amber" : "green"}`;
      document.querySelector("#budgetCheck").textContent = state === "Safe zone" ? "Budget safe" : "Budget needs review";
    }

    function selectedPublisher(data) {
      const selectedId = data.llm_selection?.selected_publisher_id;
      return (data.recommended_publishers || []).find((item) => item.id === selectedId) || (data.recommended_publishers || [])[0];
    }

    function selectedPersona(data) {
      const selectedId = data.llm_selection?.selected_persona_id;
      return (data.recommended_personas || []).find((item) => item.id === selectedId) || (data.recommended_personas || [])[0];
    }

    function activeBidRange(bid) {
      if ((bid.type || "cpm") === "cpc") return bid.starting_cpc_range_usd || bid.starting_cpm_range_usd || [1, 5];
      return bid.starting_cpm_range_usd || bid.starting_cpc_range_usd || [10, 22];
    }

    function creativeAudienceSummary(data, config) {
      const audiences = config.target_personas || [];
      const variants = data.creative_variants || [];
      const names = audiences.length ? audiences.map((item) => item.name) : variants.map((item) => item.persona_name);
      return chipList([...new Set(names.filter(Boolean))]);
    }

    function budgetAllocationSummary(config) {
      const allocation = config.budget?.allocation || [];
      if (!allocation.length) return "not provided";
      return allocation.map((item) => `${escapeHtml(item.publisher_name)} ${escapeHtml(item.budget_pct)}% (${escapeHtml(item.role || "test")})`).join("<br>");
    }

    function candidateCard(publisher) {
      return `<article class="candidate">
        <div style="display:flex;justify-content:space-between;gap:10px">
          <strong>${escapeHtml(publisher.name)}</strong>
          <span class="score">${escapeHtml(publisher.score)}</span>
        </div>
        <p>${formatNumber(publisher.monthly_impressions)} impressions - ${formatCurrency(publisher.avg_order_value_usd)} AOV</p>
        <div>${chipList([publisher.category, ...(publisher.subcategories || []).slice(0, 2)])}</div>
      </article>`;
    }

    function excludedCard(publisher) {
      return `<article class="candidate">
        <div style="display:flex;justify-content:space-between;gap:10px">
          <strong>${escapeHtml(publisher.name)}</strong>
          <span class="score">${escapeHtml(publisher.score)}</span>
        </div>
        <p>${escapeHtml((publisher.why_excluded || [])[0] || "Lower relative fit than selected publisher.")}</p>
      </article>`;
    }

    function detailRows(item) {
      const entries = Object.entries(item || {}).filter(([, value]) => value !== undefined && value !== null);
      if (!entries.length) return '<div class="detail-row"><span class="detail-key">Status</span><span class="detail-value empty-value">Not selected</span></div>';
      return entries.map(([key, value]) => `
        <div class="detail-row">
          <span class="detail-key">${escapeHtml(humanizeKey(key))}</span>
          <span class="detail-value">${detailValue(key, value)}</span>
        </div>
      `).join("");
    }

    function detailValue(key, value) {
      if (Array.isArray(value)) {
        return value.length ? chipList(value.map((item) => typeof item === "object" ? JSON.stringify(item) : String(item))) : '<span class="empty-value">none</span>';
      }
      if (value && typeof value === "object") {
        const nested = Object.entries(value);
        if (!nested.length) return '<span class="empty-value">none</span>';
        return `<span class="nested-rows">${nested.map(([nestedKey, nestedValue]) => `
          <span class="nested-row">
            <span class="nested-key">${escapeHtml(humanizeKey(nestedKey))}</span>
            <span>${detailValue(nestedKey, nestedValue)}</span>
          </span>
        `).join("")}</span>`;
      }
      if (typeof value === "boolean") return value ? "Yes" : "No";
      if (typeof value === "number") {
        if (/usd|aov|cpa|budget|spend/i.test(key)) return formatCurrency(value);
        return new Intl.NumberFormat("en-US").format(value);
      }
      if (value === "") return '<span class="empty-value">not provided</span>';
      return escapeHtml(value);
    }

    function lineItem(label, value) {
      return `<div class="line-item"><strong>${escapeHtml(label)}</strong><span>${value}</span></div>`;
    }

    function chipList(values) {
      const clean = (values || []).filter(Boolean);
      if (!clean.length) return '<span class="chip">not provided</span>';
      return clean.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
    }

    function initials(value) {
      return String(value || "?").split(/\\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
    }

    function formatCurrency(value) {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: Number(value) < 10 ? 2 : 0 }).format(Number(value || 0));
    }

    function formatNumber(value) {
      return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
    }

    function titleize(value) {
      return String(value).replace(/_/g, " ").replace(/\\b\\w/g, (char) => char.toUpperCase());
    }

    function humanizeKey(value) {
      return titleize(value).replace(/\\b(Id|Usd|Aov|Cpa)\\b/g, (match) => match.toUpperCase());
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
    }
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        self._log("GET / -> serving campaign studio UI")
        self._send(200, HTML, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/campaign":
            self.send_error(404)
            return
        started_at = time.perf_counter()
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        description = str(payload.get("description", ""))
        self._log(f"POST /api/campaign -> planner started ({len(description)} chars)")
        try:
            campaign = build_campaign(description)
        except Exception as error:
            elapsed = time.perf_counter() - started_at
            self._log(f"POST /api/campaign -> planner failed after {elapsed:.2f}s: {error}")
            self._send(500, json.dumps({"error": str(error)}), "application/json")
            return
        elapsed = time.perf_counter() - started_at
        publisher_count = len(campaign.get("recommended_publishers", []))
        variant_count = len(campaign.get("creative_variants", []))
        self._log(
            "POST /api/campaign -> planner succeeded "
            f"after {elapsed:.2f}s ({publisher_count} publishers, {variant_count} variants)"
        )
        self._send(200, json.dumps(campaign), "application/json")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _log(self, message: str) -> None:
        print(f"[adtech-demo] {message}", flush=True)

    def _send(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Adtech Campaign Architect demo.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[adtech-demo] Demo running at http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
