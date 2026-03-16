### EventBus.emit async handler bug – root cause and fix

This document describes the `EventBus.emit()` bug in `kymflow.gui_v2.bus` and how it was fixed. It’s intended as a reference when working on async handlers and the NiceGUI event bus in other branches.

---

### Overview

After moving some handlers (e.g. `SaveController` and `ImageLineViewerV2Bindings`) to `async def` and integrating with NiceGUI’s `background_tasks` and `context.client`, the app started throwing:

```text
TypeError: object NoneType can't be used in 'await' expression
```

with a traceback pointing into `bus.py` inside an inner coroutine called `task_with_context`, specifically at `await handler(event)`.

This only manifested on a feature branch, not on `main`, even though `emit()` looked similar. The reason is that there were **two interacting issues**:

1. A **late‑binding closure bug** in `EventBus.emit`.
2. At least one **invalid handler** (e.g. `None`) present in the bus subscriptions on that branch.

The closure bug is the real core problem; the invalid handler just made it visible.

---

### (i) Root problem

#### 1. Async handlers in the event bus

`EventBus.emit` is responsible for invoking all handlers subscribed for a given event type. Those handlers can be:

- **Synchronous functions** (regular controller/binding methods), or
- **Asynchronous functions** (`async def`), such as:
  - `SaveController._on_save_selected_async`
  - `SaveController._on_save_all_async`
  - `ImageLineViewerV2Bindings._on_file_selection_changed`

To support async handlers while preserving NiceGUI’s client context, `emit` was implemented roughly as:

```python
for handler, phase in filtered_handlers:
    if inspect.iscoroutinefunction(handler):
        current_client = context.client

        async def task_with_context():
            with current_client:
                await handler(event)

        background_tasks.create(task_with_context())
    else:
        handler(event)
```

- `inspect.iscoroutinefunction(handler)` detects async handlers.
- `current_client = context.client` captures the NiceGUI client context.
- `task_with_context` is scheduled via `background_tasks.create`, and later runs with that client context and calls `await handler(event)`.

#### 2. Late‑binding closure over loop variables

The subtle bug is that `task_with_context` **closes over the loop variables `handler` and `event` by reference**, not by value:

- In Python, inner functions capture outer-scope variables **by reference**.
- In the `for handler, phase in filtered_handlers:` loop:
  - `handler` and `event` are reassigned on each iteration.
  - `task_with_context` holds references to those names, not frozen values.

Consequence:

- Each iteration *appears* to create a new coroutine that will call the corresponding `handler(event)`.
- But in reality, all `task_with_context` instances share the same `handler` and `event` references.
- When the loop continues, `handler` is rebound to the next function (or something else, e.g. `None` if there’s a bug), and `event` to the next event.
- When the background task finally runs, it uses **whatever `handler` and `event` currently are**, not what they were at the time `task_with_context` was created.

This is a classic Python **late‑binding closure** pitfall.

#### 3. Interaction with a `None` or non-callable handler

On the problematic branch, a merge or surrounding change caused a **bad handler value** to get into the event bus subscriptions:

- For at least one `(event_type, phase)`, the subscription list contained something like `(None, some_phase)` or another non-callable.
- That alone would already be incorrect, but the late‑binding closure turned it into a much nastier bug:

  1. Earlier in the loop, a valid async handler `h1` was processed:
     - `task_with_context` was defined and scheduled for `h1`.
  2. Later in the same `emit` call, the loop iterated over a bad entry:
     - `handler` was bound to `None` for that iteration.
  3. Because `task_with_context` closed over `handler` by reference, when the scheduled coroutine ran, it saw `handler is None` and did:

     ```python
     await handler(event)  # handler is now None
     ```

  4. This produced:

     ```text
     TypeError: object NoneType can't be used in 'await' expression
     ```

Why it only appeared on a branch:

- On `main`, there were no invalid handlers in `_subs`, so `handler` was always callable and the late‑binding closure never hit a `None`.
- On the feature branch, the subscription set changed enough that at least one entry ended up as `None`, so the bug became visible.

So the **root cause is not “just a None handler”**. It is the combination of:

- A **late‑binding closure** over the loop variable `handler`, and
- A **bad subscription entry** that bound `handler` to a non-callable (like `None`) for a later iteration.

---

### (ii) How it was fixed

Two complementary fixes were applied inside `EventBus.emit`:

1. **Fix the closure to capture values at definition time.**
2. **Add a defensive guard to skip invalid handlers.**

The closure fix is the essential correctness change; the guard adds robustness and better diagnostics.

#### 1. Fixing the late‑binding closure

The key change is to ensure `task_with_context` captures the **current** values of `handler`, `event`, and `current_client` at the time it is defined, by using default arguments.

Conceptual change:

```python
current_client = context.client

async def task_with_context():
    with current_client:
        await handler(event)

background_tasks.create(task_with_context())
```

became:

```python
current_client = context.client

async def task_with_context(
    h=handler,
    ev=event,
    client=current_client,
):
    with client:
        await h(ev)

background_tasks.create(task_with_context())
```

Why this works:

- Default argument expressions (`h=handler`, `ev=event`, `client=current_client`) are evaluated **once** at function definition time.
- Each iteration of the loop defines a new `task_with_context` with its own bound defaults:
  - `h` is bound to the handler for that iteration.
  - `ev` is bound to the event passed to `emit`.
  - `client` is bound to the client context for that iteration.
- Later iterations can rebind `handler` and `event` without affecting any previously created `task_with_context` instances.
- When `background_tasks.create(task_with_context())` runs the coroutine, it always calls `await h(ev)` on the correct handler for the correct event, regardless of what the loop has done since.

This change alone removes the possibility that a later `handler = None` assignment can “poison” earlier scheduled tasks.

#### 2. Defensive guard for non-callable handlers

To make the bus more robust and easier to debug if an invalid handler is ever subscribed again, a guard was added at the top of the handler loop:

Conceptually:

```python
for _idx, (handler, phase) in enumerate(filtered_handlers):
    # logging of handler name, etc.
    try:
        # Skip invalid or missing handlers defensively
        if handler is None or not callable(handler):
            logger.warning(
                f"[bus] Skipping non-callable handler {handler!r} for {etype.__name__} "
                f"(phase={phase}, client={self._client_id})"
            )
            continue

        if inspect.iscoroutinefunction(handler):
            current_client = context.client

            async def task_with_context(
                h=handler,
                ev=event,
                client=current_client,
            ):
                with client:
                    await h(ev)

            background_tasks.create(task_with_context())
        else:
            handler(event)

    except Exception:
        # existing logger.exception with handler name and event type
```

Effects of the guard:

- If a `None` or otherwise non-callable handler ever gets into `_subs`:
  - It is **skipped** for that event emission instead of crashing.
  - A warning is logged with:
    - Event type (`etype.__name__`),
    - Phase,
    - Client id,
    - The bad handler value (`repr(handler)`).
- This makes it much easier to later trace where that handler came from (by grepping for the relevant `subscribe_*` call).

Importantly:

- In a healthy runtime (like the final runs after the fix), this branch is never taken:
  - All handlers are callable, so the guard does nothing.
  - The bus runs as before, but with safe closure semantics for async handlers.

---

### Practical takeaway

When using async handlers with `EventBus.emit` and NiceGUI:

1. **Always capture loop variables in async closures using default arguments.**
   - Avoid directly referencing loop variables (`handler`, `event`) inside an inner async def that is scheduled later.
   - Use the `h=handler`, `ev=event`, `client=current_client` pattern to bind current values.

2. **Defensively guard against invalid handlers.**
   - Before dispatch, check `handler is not None` and `callable(handler)`.
   - Log and skip if not, instead of letting it blow up inside `inspect.iscoroutinefunction` or `await`.

3. **Remember why this only showed up on one branch.**
   - The closure pattern existed but was latent on `main` because all handlers were valid.
   - A slightly different subscription pattern on the branch introduced an invalid handler, revealing the bug.
   - Fixing the closure makes the bus correct in all branches; the guard helps detect and survive future subscription mistakes.

