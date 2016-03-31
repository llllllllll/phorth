from sys import settrace, gettrace

from .code import build_phorth_ctx
from .primitives import Done
from ._runner import jump_handler


def _tracer(*args):
    return _tracer


def run_phorth(stack_size=30000, memory=65535):
    """Run a phorth session.

    Parameters
    ----------
    stack_size : int, optional
        The size of the stack to build in the phorth frame.
    memory : int, optional
        The size of the memory space for the phorth context. This translates
        to the size of the `co_code` of the context.
    """
    here, ctx = build_phorth_ctx(stack_size, memory)
    # set a tracer to enable some features in PyFrame_EvalFrameEx
    old_trace = gettrace()
    settrace(_tracer)
    try:
        jump_handler(ctx(
            immediate=True,
            here=here,
            latest=None,
            cstack=[],
            stack_size=0,
            literals=[],
        ))
    except Done:
        return None
    finally:
        settrace(old_trace)  # reset the old tracer.
