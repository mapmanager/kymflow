# chatgpt_rules.md (Project guardrails)

## 1) Always use current source of truth
- Use the files uploaded in the *current prompt* as the source of truth.
- If you have not opened/read an uploaded file you reference, say so and ask for it (do not guess).

## 2) Ask, don’t guess
- If an answer depends on code you cannot see, request the specific file(s).
- If multiple versions of a file may exist, ask which path/version is canonical.

## 3) No backward compatibility unless explicitly requested
- Do not propose or add defaults/fallbacks/guards “for compatibility” unless asked.
- Prefer fail-fast contracts for required fields (roi_id, roi_bounds, channel_id, etc).

## 4) Keep boundaries clean
- Respect module boundaries and “only X may import Y” rules.
- When drafting tickets, restate the boundary rules in the ticket itself.

## 5) Be concrete
- When asked “what do I change?”, respond with:
  - exact file name(s)
  - exact before/after code blocks
  - the smallest change that satisfies the requirement

## 6) Don’t churn unrelated code
- Avoid opportunistic refactors while fixing a targeted issue.
- If you spot a separate issue, propose a follow-up ticket instead of mixing.

## 7) Preserve logging
- Do not remove `logger = logging.getLogger(__name__)` patterns unless asked.

## 8) Tickets must be explicit enough for Codex
- Include acceptance criteria and “no back-compat defaults” language when relevant.
- List required updated tests and exact files to touch.
