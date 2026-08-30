# Compensability — D49

Risk tier and compensability are **different axes**. A high-risk, fully
compensable action (a refund — reversible by a chargeback) is a completely
different design problem from a low-risk, non-compensable one (an email
that has already been sent). Treating them as one scalar ("risk = 0.82")
is indefensible to a regulator; naming the axis and the class is.

## The table

| Action | Compensating action | Class |
|---|---|---|
| `issue_refund` | `reverse_refund` | FULLY compensable |
| `update_entitlement` | `restore_entitlement` | PARTIALLY (window-bounded) |
| `send_customer_email` | — | NOT compensable |
| `send_document` | `revoke_access` | PARTIALLY (it was already read) |

Implemented in `controlplane/compensation.py::compensation_for(tool)`. Every
tool registered with `dispatch_tool` needs a row — a missing one raises
loudly rather than defaulting to a guess about how reversible it is.

## How compensability drives intervention (`controlplane/decide.py`)

1. **Not compensable + verdict ≠ VERIFIED → BLOCK.** There is no undo for
   this class, so irreversibility dominates severity regardless of how the
   verdict was reached. Only ~0.8% of agent actions are estimated to be
   genuinely irreversible — the strict path is narrow by construction,
   which is what makes it affordable to be this strict.
2. **Low confidence never blocks (D3).** A contradiction driven purely by a
   C3 (semantic/grounding) check — never a hard C1/C2 predicate failure —
   escalates instead of blocking, because C3's ceiling is published SOTA
   (77.4% on LLM-AggreFact), not certainty.
3. **A hard contradiction (a real C1/C2 predicate failed) blocks**, even on
   a compensable action — compensability is about what happens if a wrong
   action gets through some other way, not a license to proceed on a known
   contradiction.
4. **UNVERIFIABLE / SOURCE_UNRELIABLE** fall back to the manifest's
   `verdict_handling` entry for that verdict (`escalate` or
   `allow_with_caveat`, which becomes MODIFY), or its `fail_posture` for
   the action's compensability class if the manifest doesn't specify.
5. **MODIFY is subtractive or additive only** — redact, caveat, constrain.
   Never substitutive: rewriting a wrong conclusion into a right one would
   require a better model than the one being checked (D8).

Escalation rate-limiting against the manifest's `escalation_budget_pct` is
implemented at `dispatch_tool`, not inside `decide()` — that requires state
(how many decisions has this session escalated already?), and `decide()`
must stay pure (hard constraint #4: no I/O, no clock, no logging) so S15's
metamorphic invariants and the mutation harness can hammer it thousands of
times. The caller owns the rolling window, persistent pending queue, and
fail-posture fallback. The pure `decide()` mutation harness still cannot
observe that caller-level state; its `escalation_budget_exceeded` operator
documents the harness boundary, not a missing runtime control.
