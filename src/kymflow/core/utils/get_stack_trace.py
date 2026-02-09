import inspect
from pathlib import Path

def get_stack_trace() -> str:
    caller_frame = inspect.stack()[2]

    # Extract details
    caller_name = caller_frame.function
    caller_filename = caller_frame.filename
    caller_lineno = caller_frame.lineno

    _ret = f"  calling fn:{caller_name} {Path(caller_filename).name}, line:{caller_lineno}"
    return _ret
