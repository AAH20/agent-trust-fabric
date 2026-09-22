"""Human-readable rendering of a local Agent Passport bundle."""

from __future__ import annotations

from html import escape
from typing import Any


def render_markdown(bundle: dict[str, Any]) -> str:
    passport = bundle["passport"]
    rows = [
        "# Agent Passport — local reference case",
        "",
        f"Case: `{bundle['case_id']}` · Events: **{passport['events']}** · Allowed: **{passport['allowed']}** · Denied: **{passport['denied']}**",
        "",
        f"Chain tip: `{bundle['chain_tip_sha256']}`",
        "",
        f"Evidence status: **{passport['evidence_status']}**",
        "",
        "| # | Source | Action | Resource | Decision | Reason |",
        "|---:|---|---|---|---|---|",
    ]
    for receipt in bundle["receipts"]:
        cells = [
            receipt["sequence"], receipt["source"], receipt["action"],
            receipt["resource"], receipt["decision"], ", ".join(receipt["reasons"]),
        ]
        rows.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in cells) + " |")
    rows.extend([
        "", "## Interpretation", "",
        "This report shows deterministic evaluation of caller-asserted events. It does not prove producer identity,",
        "tool execution, payment outcome, or an external approval. Re-run verification against the original case",
        "and use independent identity, signatures, trusted clocks, and durable storage for production evidence.",
        "",
    ])
    return "\n".join(rows)


def render_html(bundle: dict[str, Any]) -> str:
    """Create a portable static viewer; escape all fixture-controlled text."""
    passport = bundle["passport"]
    cards = []
    for receipt in bundle["receipts"]:
        state = receipt["decision"]
        details = " · ".join(receipt["reasons"])
        cards.append(
            f'<article class="event {escape(state)}" data-decision="{escape(state)}">'
            f'<div class="event-top"><span>#{receipt["sequence"]:02d} · {escape(receipt["source"])}'
            f'</span><strong>{escape(state.upper())}</strong></div>'
            f'<h3>{escape(receipt["action"])}</h3>'
            f'<p class="resource">{escape(receipt["resource"])}</p>'
            f'<p class="reason">{escape(details)}</p>'
            f'<code>receipt {escape(receipt["sha256"][:18])}…</code>'
            '</article>'
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Passport — {escape(str(bundle['case_id']))}</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#e8edf6;background:#08101c}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:radial-gradient(circle at 85% 5%,#173758 0,transparent 32%),#08101c}}
main{{max-width:1060px;margin:auto;padding:58px 24px 96px}}.eyebrow{{letter-spacing:.16em;text-transform:uppercase;color:#7fb6db;font-size:.8rem}}
h1{{font-size:clamp(2.5rem,6vw,5.2rem);letter-spacing:-.06em;line-height:1;margin:14px 0}}.lead{{color:#a7b9ce;max-width:720px;line-height:1.65}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:34px 0}}.stat,.event,.proof{{background:#101e2e;border:1px solid #29415b;border-radius:16px;padding:20px}}
.stat strong{{display:block;font-size:2rem}}.stat span{{color:#a7b9ce}}.bar{{display:flex;gap:9px;align-items:center;margin:38px 0 20px;flex-wrap:wrap}}
button{{border:1px solid #38506b;background:#132338;color:#e8edf6;border-radius:999px;padding:9px 17px;cursor:pointer}}button[aria-pressed="true"]{{background:#67d5c0;color:#06201c;border-color:#67d5c0}}
.events{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}}.event{{min-height:232px}}.event.deny{{border-top:3px solid #f2a474}}.event.allow{{border-top:3px solid #67d5c0}}
.event-top{{display:flex;justify-content:space-between;color:#aac0d6;font-size:.82rem}}.event-top strong{{color:#e8edf6}}h3{{font-size:1.2rem;margin:26px 0 8px}}
.resource,.reason{{overflow-wrap:anywhere}}.resource{{color:#d6e4f1}}.reason{{color:#a7b9ce}}code{{font:12px ui-monospace,monospace;color:#7fb6db;overflow-wrap:anywhere}}
.proof{{margin-top:28px}}.proof h2{{margin-top:0}}.proof p{{color:#b4c5d7;line-height:1.65}}.warning{{color:#ffd49b!important}}
@media(max-width:580px){{.stats{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<div class="eyebrow">A2Z SOC · Local reference case</div><h1>Agent Passport</h1>
<p class="lead">A portable view of action-intent decisions and local evidence receipts. This viewer shows deterministic fixture results, not a production agent run or proof that an external tool executed.</p>
<div class="stats"><div class="stat"><strong>{passport['events']}</strong><span>Action intents</span></div><div class="stat"><strong>{passport['allowed']}</strong><span>Allowed</span></div><div class="stat"><strong>{passport['denied']}</strong><span>Denied</span></div></div>
<div class="bar" role="group" aria-label="Filter events"><button type="button" aria-pressed="true" data-filter="all">All</button><button type="button" aria-pressed="false" data-filter="allow">Allowed</button><button type="button" aria-pressed="false" data-filter="deny">Denied</button></div>
<section class="events" aria-label="Action receipts">{''.join(cards)}</section>
<section class="proof"><h2>What this proves</h2><p>The receipt chain can be checked against the original case. Its current tip is <code>{escape(bundle['chain_tip_sha256'])}</code>.</p>
<p class="warning">Evidence status: {escape(passport['evidence_status'])}. Producer identity, external approval, tool execution, and payment outcome are not authenticated by this local demonstration.</p></section>
</main><script>for(const b of document.querySelectorAll('[data-filter]')){{b.addEventListener('click',()=>{{const f=b.dataset.filter;for(const x of document.querySelectorAll('[data-filter]'))x.setAttribute('aria-pressed',String(x===b));for(const e of document.querySelectorAll('[data-decision]'))e.hidden=f!=='all'&&e.dataset.decision!==f}})}}</script></body></html>
'''
