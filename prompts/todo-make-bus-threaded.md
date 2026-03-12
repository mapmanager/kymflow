work on bus.


Context: I am evaluating a performance optimization for our current EventBus in kymflow/bus.py. Currently, our emit() function dispatches events to 15+ listeners sequentially, which blocks the NiceGUI main thread and causes UI "freezes" during heavy operations like SetFile.

Task: Please review the attached "High-Performance NWBus Roadmap" as a potential strategy. This is a suggestion, not a direct command. I want you to weigh this approach against our existing implementation in gui_v2/ and core/ and provide your technical assessment.

Please evaluate based on:

Pros/Cons: Analyze the benefits of non-blocking dispatch versus the risks of thread-safety/race conditions in our specific view-bindings.

Implementation Feasibility: How naturally does the _dispatch logic (using run_in_executor) fit into our current EventBus.emit() phase-filtering?

State Contention: Identify any specific listeners in our gui_v2/ that might conflict if run in parallel (e.g., multiple handlers writing to the same plot_dict).

Alternative Ideas: If you see a safer or more "NiceGUI-native" way to achieve this responsiveness, please propose it.

Goal: Do not apply these changes yet. Provide a summary of your findings and tell me if you believe this is the correct "source of truth" for our next refactor.


## High-Performance NWBus Roadmap

1. Objective
Enable the EventBus to offload heavy synchronous tasks to background threads and execute async handlers concurrently. This preserves the NiceGUI main thread for UI heartbeats, keeping the interface fluid during massive state changes (like SetFile).

2. The Core Refactor: emit()
The primary change is replacing the sequential handler(event) call with an intelligent dispatcher that identifies the "cost" of the handler.

Updated EventBus.emit Specification

```
import asyncio
from nicegui import core

# Inside class EventBus:
def emit(self, event: Any) -> None:
    etype = type(event)
    all_handlers = self._subs.get(etype, [])
    
    # ... [Keep your existing phase filtering logic here] ...
    filtered_handlers = self._get_filtered_handlers(all_handlers, event)

    for handler, _ in filtered_handlers:
        self._dispatch(handler, event)

def _dispatch(self, handler: Callable, event: Any) -> None:
    """Intelligent dispatching based on handler type."""
    try:
        if asyncio.iscoroutinefunction(handler):
            # Non-blocking: Schedules the async def on the NiceGUI loop
            core.loop.create_task(handler(event))
        else:
            # Non-blocking: Offloads the standard def to a background thread
            # 'None' uses the default ThreadPoolExecutor
            core.loop.run_in_executor(None, handler, event)
            
        if self._config.trace:
            logger.debug(f"[bus] Dispatched {handler.__qualname__} for {type(event).__name__}")
    except Exception:
        logger.exception(f"[bus] Failed to dispatch {handler.__qualname__}")
```

3. Migration Guide: From Sync to Async-Aware
This guide is for the developers refactoring the gui_v2/ and core/ listeners.

Step 1: Identify "IO-Heavy" vs "UI-Heavy"
Keep as def (Threaded): Functions that load files (load_channel), perform heavy NumPy math, or do disk I/O. These will now run in background threads automatically.

Change to async def (Asyncio): Functions that perform many small NiceGUI updates, wait for timers, or call external async APIs.

Step 2: Thread-Safety in Bindings
When a handler runs in a background thread (via run_in_executor), calling NiceGUI UI methods is generally safe, but for massive updates, use await or ui.run_javascript if you transition to async.

Before (Synchronous/Blocking):

```
def _on_file_selection_changed(self, e: FileSelection) -> None:
    # This blocks the bus until loading is done
    self._view.set_selected_file(e.file, e.channel, e.roi_id)
```

After (Automatic Threading):
The code above remains exactly the same. Because it is a def, the new NWBus will push it to a thread. The GUI stays alive while set_selected_file loads the data.

Step 3: Handling State Contention
Because 15+ listeners are now running simultaneously in different threads:

Avoid Global Mutables: Ensure listeners aren't all trying to pop() or clear() the same global list at once.

Use ui.update(): If a listener finishes its threaded work, calling self.plot.update() is thread-safe in NiceGUI.

4. Implementation Checklist for LLM Refactor
[ ] Modify bus.py: Import asyncio and nicegui.core.

[ ] Update EventBus.emit: Implement the _dispatch helper using iscoroutinefunction and run_in_executor.

[ ] Trace Logic: Ensure the existing trace logic accounts for "Dispatch" vs "Completion" (since events are now fire-and-forget).

[ ] Verify Client Isolation: Ensure core.loop tasks are correctly associated with the client context (NiceGUI handles this usually, but keep it in mind).

5. Why this fixes your SetFile lag
When SetFile is emitted:

The EventBus loop runs in microseconds. It fires off 15 tasks to the thread pool and returns immediately.

NiceGUI continues to render the "loading" state or handles mouse movements.

As each of the 15 listeners finishes its load_channel and plot_dict updates in its own thread, the browser receives the updates incrementally.


6. Safety & Observability: The "Background Sentinel"
When moving to a non-blocking emit(), we must ensure that exceptions occurring in background threads are captured, associated with the specific client_id, and logged to your existing kymflow logger.

The Background Wrapper (bus.py)

```
import functools

def _wrap_handler(self, handler: Callable, event: Any):
    """Wraps a handler to ensure background exceptions are logged correctly."""
    handler_name = getattr(handler, "__qualname__", repr(handler))
    
    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception:
            logger.exception(
                f"[bus] Background Exception in {handler_name} "
                f"for {type(event).__name__} (client={self._client_id})"
            )
    return wrapper

def _dispatch(self, handler: Callable, event: Any) -> None:
    """The Final High-Performance Dispatcher."""
    # Wrap the handler with our safety sentinel
    safe_handler = self._wrap_handler(handler, event)
    
    if asyncio.iscoroutinefunction(handler):
        # Async handlers are scheduled on the loop
        core.loop.create_task(safe_handler(event))
    else:
        # Sync handlers are offloaded to the thread pool
        # This keeps the NiceGUI UI thread 100% responsive
        core.loop.run_in_executor(None, safe_handler, event)
```

7. Key Migration Rules for Kymflow Developers
To prevent race conditions now that 15+ listeners run in parallel, developers must follow these "Thread-Safe UI" rules:

Read-Only Shared State: Listeners can safely read from the KymImage or FileSelection event simultaneously.

Atomic UI Updates: When updating a Plotly dict or a NiceGUI label, do it in a single block. Avoid "partial" updates where one thread changes the X-axis and another changes the Y-axis of the same plot at the same time.

The SetFile Sequence: If certain widgets must update before others (e.g., the Image ROI must exist before the Line Plot can draw), use the Event Phase system already in your bus (intent vs state) to sequence them, rather than relying on the order of the for loop.

Summary for the LLM Refactor
Input: Existing kymflow/bus.py and gui_v2/ bindings.

Task: Implement the NWBus logic inside the existing EventBus class.

Outcome: A SetFile event that used to freeze the app for 4 seconds now returns control to the user in ~5 milliseconds, with widgets "popping in" as their background threads finish.



