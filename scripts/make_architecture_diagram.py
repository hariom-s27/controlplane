"""Deterministic generator for docs/architecture.png and docs/architecture.svg.

Every node and every non-trivial arrow below corresponds to a concept that
actually exists in this repository at the time this file was written:

  AI AGENT / PROPOSED TOOL CALL       -> agents/*.py calling dispatch_tool()
  dispatch_tool()                     -> controlplane/intercept.py
  GOVERNANCE GATE (session.gate_enabled / CP_GATE) -> controlplane/intercept.py,
                                          controlplane/schema.py, .env.example
  GATE OFF / negative control         -> intercept.dispatch_tool(): if not
                                          session.gate_enabled: return impl(**args)
                                          (no claims, evidence, predicate
                                          evaluation, decide(), or receipt)
  AI CLAIMS                           -> controlplane/extract.py
                                          (extract_action / build_claims)
  COMPANY FACTS                       -> controlplane/registry/* resolvers
                                          (orders.py, policy.py,
                                          entitlements.py) reading
                                          orders.db / policy_store.db /
                                          entitlements.db
  POLICY / MANIFEST                   -> manifests/<name>.yaml,
                                          controlplane/manifest.py,
                                          controlplane/bindings.py
                                          (predicate_payload, authority
                                          ceiling, window, reliability floor)
  PREDICATE / EVIDENCE EVALUATION     -> controlplane/bindings.py
                                          (build_predicate_payload) +
                                          controlplane/predicates/__init__.py
                                          (Zen JDM graph evaluate())
  decide()                            -> controlplane/decide.py
  VERDICT / INTERVENTION              -> controlplane/schema.py Verdict /
                                          Intervention enums
  SIGNED DECISION RECEIPT             -> controlplane/receipt.py
                                          (build_receipt, HMAC-signed,
                                          built at decide()/record() time,
                                          before execution)
  EXECUTION CONTROL / EXECUTE /
  PREVENT-REFUSE                      -> intercept.dispatch_tool()'s branch
                                          on decision.intervention
  RUNTIME EXECUTION STATE             -> intercept._execute_governed_once()
                                          (controlplane/idempotency.py
                                          ExecutionLedger), recorded as a
                                          SEPARATE follow-up trail entry —
                                          never folded into the signed
                                          receipt's own bytes
  AUDIT TRAIL                         -> controlplane/receipt.py
                                          OPERATIONAL_TRAIL (decisions.jsonl),
                                          written by controlplane/telemetry.py

Nothing here is fabricated: no risk engine, no LLM judge, no human-review
service, no database beyond the three named company systems, no generic
"policy engine" box standing in for something that doesn't exist.

Every box is placed by its TOP edge and its height is computed from its
actual label/subtitle line counts (see content_height()), so nothing here
is hand-tuned pixel math that silently breaks when a line of text changes.

Run twice from the same source tree -> byte-for-byte identical output
(fixed hashsalt, no timestamps, no random IDs, no machine-specific paths).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "controlplane-architecture-v1"
matplotlib.rcParams["path.simplify"] = False
matplotlib.rcParams["font.family"] = "DejaVu Sans"

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "docs" / "architecture.png"
OUT_SVG = ROOT / "docs" / "architecture.svg"

# ---------------------------------------------------------------------------
# Palette (restrained, distinctions carried by label + border style, not
# color alone)
# ---------------------------------------------------------------------------
INK = "#1E2430"
MUTED = "#5A6376"
NEUTRAL_FILL = "#F5F6F8"
NEUTRAL_BORDER = "#33415C"
CLAIMS_FILL = "#FFF3E0"
CLAIMS_BORDER = "#B15C00"
FACTS_FILL = "#E8F1FB"
FACTS_BORDER = "#1F5C99"
POLICY_FILL = "#EAF7EE"
POLICY_BORDER = "#1B7A3D"
EVAL_FILL = "#EEEBFB"
EVAL_BORDER = "#4B3F8C"
RECEIPT_FILL = "#FDF6E2"
RECEIPT_BORDER = "#8A6D1D"
AUDIT_FILL = "#E7E9F5"
AUDIT_BORDER = "#21283B"
BYPASS_FILL = "#FBEAE8"
BYPASS_BORDER = "#A32A1E"
EXEC_FILL = "#EAF7EE"
EXEC_BORDER = "#1B7A3D"
REFUSE_FILL = "#FBEAE8"
REFUSE_BORDER = "#A32A1E"
WRAP_BORDER = "#8891A0"

FIG_W = 1200.0

fig, ax = plt.subplots(figsize=(12.0, 18.6), dpi=150)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

LINE_FACTOR = 1.38  # points -> data-unit line height multiplier (data units == 1/100 inch)


def _pt_to_du(pt):
    return pt / 72.0 * 100.0


def _lines(text):
    return text.count("\n") + 1


def content_height(label, label_size, sub, sub_size, top_pad, bottom_pad, gap):
    h = top_pad + _lines(label) * _pt_to_du(label_size) * LINE_FACTOR
    if sub:
        h += gap + _lines(sub) * _pt_to_du(sub_size) * LINE_FACTOR
    return h + bottom_pad


def box(cx, top, w, label, sub=None, *, fill=NEUTRAL_FILL, border=NEUTRAL_BORDER,
        lw=1.8, ls="solid", label_size=15, sub_size=11.2, bold=True, z=3,
        top_pad=13, bottom_pad=11, gap=7, min_h=0):
    """A rounded box whose TOP edge is placed at ``top``; height is computed
    from label/sub line counts (never hand-tuned, so it can't collide with
    its own border no matter how a line is edited)."""
    h = max(min_h, content_height(label, label_size, sub, sub_size, top_pad, bottom_pad, gap))
    cy = top - h / 2
    x0, y0 = cx - w / 2, cy - h / 2
    patch = FancyBboxPatch(
        (x0, y0), w, h,
        boxstyle="round,pad=0,rounding_size=8",
        linewidth=lw, edgecolor=border, facecolor=fill, linestyle=ls, zorder=z,
    )
    ax.add_patch(patch)
    if sub:
        ax.text(cx, cy + h / 2 - top_pad, label, ha="center", va="top",
                 fontsize=label_size, fontweight="bold" if bold else "normal",
                 color=INK, zorder=z + 1, linespacing=LINE_FACTOR)
        ax.text(cx, cy - h / 2 + bottom_pad, sub, ha="center", va="bottom",
                 fontsize=sub_size, color=INK, zorder=z + 1, linespacing=LINE_FACTOR)
    else:
        ax.text(cx, cy, label, ha="center", va="center",
                 fontsize=label_size, fontweight="bold" if bold else "normal",
                 color=INK, zorder=z + 1)
    return {"cx": cx, "cy": cy, "w": w, "h": h, "top": top, "bottom": top - h}


def arrow(p0, p1, *, color=NEUTRAL_BORDER, lw=1.6, style="-|>", ls="solid", z=2,
          connectionstyle="arc3,rad=0.0"):
    a = FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=14, linewidth=lw,
        color=color, linestyle=ls, zorder=z, connectionstyle=connectionstyle,
        shrinkA=0, shrinkB=0,
    )
    ax.add_patch(a)


def down(b, gap):
    arrow((b["cx"], b["bottom"]), (b["cx"], b["bottom"] - gap))
    return b["bottom"] - gap


def tag(cx, cy, text, *, size=11.5, color=INK, weight="normal", style="normal"):
    ax.text(cx, cy, text, ha="center", va="center", fontsize=size, color=color,
             fontweight=weight, fontstyle=style, zorder=4)


GAP = 30
CX = 600.0
cursor = 1830.0

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
ax.text(FIG_W / 2, cursor, "CONTROLPLANE", ha="center", va="top",
         fontsize=27, fontweight="bold", color=INK)
ax.text(FIG_W / 2, cursor - 34, "GOVERNANCE / DECISION ARCHITECTURE", ha="center", va="top",
         fontsize=15.5, fontweight="bold", color="#4A5468")
ax.text(FIG_W / 2, cursor - 60, "the runtime path a governed tool call takes, from proposed action to signed, auditable decision",
         ha="center", va="top", fontsize=11.5, color=MUTED, fontstyle="italic")
cursor -= 100
title_top = 1830.0

# ---------------------------------------------------------------------------
# Top spine: agent -> proposed tool call -> dispatch_tool() -> gate
# ---------------------------------------------------------------------------
b_agent = box(CX, cursor, 280, "AI AGENT", sub="agents/*.py — proposes a tool call")
cursor = down(b_agent, GAP)

b_call = box(CX, cursor, 340, "PROPOSED TOOL CALL", sub="tool name, args, justification, retrieved chunks")
cursor = down(b_call, GAP)

b_dispatch = box(CX, cursor, 440, "dispatch_tool()",
                  sub="controlplane/intercept.py — interception choke point",
                  fill=EVAL_FILL, border=EVAL_BORDER)
cursor = down(b_dispatch, GAP)

b_gate = box(CX, cursor, 380, "GOVERNANCE GATE", sub="session.gate_enabled   (CP_GATE = on | off)")
gate_bottom = b_gate["bottom"]

# ---------------------------------------------------------------------------
# Gate ON / OFF split
# ---------------------------------------------------------------------------
gate_left_x, gate_right_x = 380.0, 930.0
split_y = gate_bottom - 46

arrow((CX - 80, gate_bottom), (gate_left_x, split_y), connectionstyle="arc3,rad=-0.15")
tag(gate_left_x - 58, split_y + 40, "ON", size=13, weight="bold", color=EXEC_BORDER)

arrow((CX + 80, gate_bottom), (gate_right_x, split_y), connectionstyle="arc3,rad=0.15")
tag(gate_right_x + 62, split_y + 40, "OFF", size=13, weight="bold", color=BYPASS_BORDER)

# NEGATIVE CONTROL — dead-end branch, placed top-down from split_y
b_bypass = box(gate_right_x, split_y - 20, 360,
               "NEGATIVE CONTROL\nGOVERNANCE BYPASSED",
               sub="dispatch_tool(): return impl(**args)\nno claims · no evidence · no predicate eval\nno decide() · no signed receipt",
               fill=BYPASS_FILL, border=BYPASS_BORDER, ls=(0, (6, 3)), lw=2.0,
               label_size=14, sub_size=10.6, top_pad=15, bottom_pad=13)
arrow((gate_right_x, split_y), (gate_right_x, b_bypass["top"]))

# GOVERNED PATH tag on the ON branch
tag(gate_left_x, split_y - 22, "GOVERNED PATH", size=12.5, weight="bold", color=EVAL_BORDER)
governed_tag_bottom = split_y - 22 - 16
wrap_top = governed_tag_bottom - 6

# The governed column continues from wrap_top; it must also clear the
# (much taller) negative-control dead-end branch before the two visually
# reconverge in the same horizontal band (the three-lane row spans the
# full width, including the x-range under the bypass box).
lanes_top = min(wrap_top - 46, b_bypass["bottom"] - GAP)

# ---------------------------------------------------------------------------
# Three input lanes: AI CLAIMS / COMPANY FACTS / POLICY-MANIFEST
# ---------------------------------------------------------------------------
tag(CX, lanes_top + 14, "three distinct conceptual inputs — never merged before evaluation",
    size=11, color=MUTED, style="italic")

lane_w = 300
x_claims, x_facts, x_policy = 260.0, 600.0, 940.0
lane_top = lanes_top - 14

b_claims = box(x_claims, lane_top, lane_w, "AI CLAIMS",
               sub="extract_action() / build_claims()\njustification + retrieved chunks\nHYPOTHESIS — not fact",
               fill=CLAIMS_FILL, border=CLAIMS_BORDER, ls=(0, (5, 3)),
               label_size=14.5, sub_size=10.4)

b_facts = box(x_facts, lane_top, lane_w, "COMPANY FACTS",
              sub="registry resolvers (registry/*)\norders.db · policy_store.db\n· entitlements.db",
              fill=FACTS_FILL, border=FACTS_BORDER,
              label_size=14.5, sub_size=10.4)

b_policy = box(x_policy, lane_top, lane_w, "POLICY / MANIFEST",
               sub="manifests/<use_case>.yaml\npredicate_graph, authority ceiling,\nwindow, reliability floor",
               fill=POLICY_FILL, border=POLICY_BORDER,
               label_size=14.5, sub_size=10.4)

arrow((gate_left_x, governed_tag_bottom), (x_facts, b_facts["top"]), connectionstyle="arc3,rad=-0.08")

lane_bottom = min(b_claims["bottom"], b_facts["bottom"], b_policy["bottom"])
cursor = lane_bottom - GAP

# ---------------------------------------------------------------------------
# Converge into predicate / evidence evaluation
# ---------------------------------------------------------------------------
b_eval = box(CX, cursor, 620, "PREDICATE / EVIDENCE EVALUATION",
             sub="bindings.build_predicate_payload()  →  predicates.evaluate()  (Zen JDM graph)",
             fill=EVAL_FILL, border=EVAL_BORDER, label_size=15, sub_size=11.2)

arrow((x_claims, lane_bottom), (b_eval["cx"] - 170, b_eval["top"]), color=CLAIMS_BORDER, connectionstyle="arc3,rad=-0.15")
arrow((x_facts, lane_bottom), (b_eval["cx"], b_eval["top"]), color=FACTS_BORDER)
arrow((x_policy, lane_bottom), (b_eval["cx"] + 170, b_eval["top"]), color=POLICY_BORDER, connectionstyle="arc3,rad=0.15")

cursor = down(b_eval, GAP)

# ---------------------------------------------------------------------------
# decide()
# ---------------------------------------------------------------------------
b_decide = box(CX, cursor, 300, "decide()", sub="controlplane/decide.py — pure function",
               fill=EVAL_FILL, border=EVAL_BORDER, label_size=17, sub_size=11.2)
cursor = down(b_decide, GAP)

# ---------------------------------------------------------------------------
# Verdict -> Intervention
# ---------------------------------------------------------------------------
b_verdict = box(CX, cursor, 680, "VERDICT",
                sub="VERIFIED  ·  CONTRADICTED  ·  UNVERIFIABLE  ·  SOURCE_UNRELIABLE",
                label_size=15, sub_size=11.2)
cursor = down(b_verdict, GAP)

b_interv = box(CX, cursor, 720, "INTERVENTION",
               sub="ALLOW  ·  MODIFY  ·  OBSERVE_ONLY  ·  ESCALATE  ·  BLOCK",
               label_size=15, sub_size=11.2)
interv_bottom = b_interv["bottom"]
split2_y = interv_bottom - 46

# ---------------------------------------------------------------------------
# Split: signed receipt (left) vs execution control (right)
# ---------------------------------------------------------------------------
recv_x, exec_x = 320.0, 850.0

arrow((CX - 90, interv_bottom), (recv_x, split2_y), connectionstyle="arc3,rad=-0.12")
b_receipt = box(recv_x, split2_y - 12, 320, "SIGNED DECISION\nRECEIPT",
                sub="receipt.py build_receipt()\nHMAC-signed at decision time,\nbefore execution",
                fill=RECEIPT_FILL, border=RECEIPT_BORDER, label_size=14, sub_size=10.4)

arrow((CX + 90, interv_bottom), (exec_x, split2_y), connectionstyle="arc3,rad=0.12")
b_execctl = box(exec_x, split2_y - 12, 320, "EXECUTION CONTROL",
                sub="dispatch_tool() branches on\ndecision.intervention",
                label_size=14.5, sub_size=10.6)

recv_bottom = b_receipt["bottom"]
execctl_bottom = b_execctl["bottom"]
branch3_top = min(recv_bottom, execctl_bottom) - GAP

# EXECUTE / PREVENT-REFUSE
ex_x, pr_x = 700.0, 1010.0
branch3_split = branch3_top - 40

arrow((exec_x - 60, execctl_bottom), (ex_x, branch3_split), connectionstyle="arc3,rad=-0.12")
b_execute = box(ex_x, branch3_split - 10, 190, "EXECUTE", sub="ALLOW / MODIFY",
                fill=EXEC_FILL, border=EXEC_BORDER, label_size=13.5, sub_size=10.6)

arrow((exec_x + 60, execctl_bottom), (pr_x, branch3_split), connectionstyle="arc3,rad=0.12")
b_prevent = box(pr_x, branch3_split - 10, 270, "PREVENT / REFUSE",
                sub="Blocked raised (BLOCK) /\nPending enqueued (ESCALATE)\n— not executed",
                fill=REFUSE_FILL, border=REFUSE_BORDER, label_size=13.5, sub_size=10.0)

cursor = down(b_execute, GAP)

b_runtime = box(ex_x, cursor, 320, "RUNTIME EXECUTION\nSTATE",
                sub="_execute_governed_once()\nExecutionLedger, at-most-once,\nrecorded as a follow-up entry",
                label_size=13.5, sub_size=10.2)
runtime_bottom = b_runtime["bottom"]

# receipt column runs straight down to merge height, then bends into audit trail
arrow((recv_x, recv_bottom), (recv_x, runtime_bottom))

# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
audit_top = min(runtime_bottom, recv_bottom) - GAP
b_audit = box(CX, audit_top, 500, "AUDIT TRAIL",
              sub="decisions.jsonl — append-only, every governed decision",
              fill=AUDIT_FILL, border=AUDIT_BORDER, lw=2.2, label_size=16, sub_size=11.5,
              top_pad=15)

arrow((recv_x, runtime_bottom), (CX - 115, b_audit["top"]), connectionstyle="arc3,rad=0.12", color=RECEIPT_BORDER)
arrow((ex_x, runtime_bottom), (CX + 115, b_audit["top"]), connectionstyle="arc3,rad=-0.12", color=NEUTRAL_BORDER)

audit_bottom = b_audit["bottom"]

# ---------------------------------------------------------------------------
# Wrapper around the governed path, sized to what it actually contains
# ---------------------------------------------------------------------------
wrap_bottom = audit_bottom - 28
wrap_x0 = 70
wrap_x1 = min(1130, gate_right_x + 190)
wrap = FancyBboxPatch((wrap_x0, wrap_bottom), wrap_x1 - wrap_x0, wrap_top - wrap_bottom,
                       boxstyle="round,pad=0,rounding_size=14",
                       linewidth=1.4, edgecolor=WRAP_BORDER, facecolor="none",
                       linestyle=(0, (4, 3)), zorder=1)
ax.add_patch(wrap)
ax.text(wrap_x0 + 18, wrap_top - 20, "GOVERNED PATH", ha="left", va="center",
        fontsize=12, color=WRAP_BORDER, fontweight="bold")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
footer1_y = wrap_bottom - 42
ax.text(FIG_W / 2, footer1_y,
        "scope: ControlPlane decision / governance architecture — not web, auth, CI/CD, or benchmark infrastructure",
        ha="center", va="center", fontsize=10.5, color=MUTED, fontstyle="italic")
footer2_y = footer1_y - 26
ax.text(FIG_W / 2, footer2_y,
        "generated deterministically by scripts/make_architecture_diagram.py from source SHA 66b832c487042fc487177c07bfc2af04ff9e2b9d",
        ha="center", va="center", fontsize=9.5, color="#8891A0")

bottom_edge = footer2_y - 30
top_edge = title_top + 20
fig_h = top_edge - bottom_edge
ax.set_xlim(0, FIG_W)
ax.set_ylim(bottom_edge, top_edge)
fig.set_size_inches(12.0, fig_h / 100.0)

fig.tight_layout(pad=0.4)

OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_PNG, dpi=150, facecolor="white", metadata={"Software": "controlplane-architecture-generator"})
fig.savefig(OUT_SVG, metadata={"Date": None, "Creator": "controlplane-architecture-generator"})

print(f"wrote {OUT_PNG}")
print(f"wrote {OUT_SVG}")
