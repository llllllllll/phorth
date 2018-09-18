from sys import settrace, gettrace


from .code import build_phorth_ctx
from .words import repl_word_impl, Done
from ._runner import jump_handler


def _tracer(*args):
    return _tracer


version = '0.2.0'


_header = """\
phorth {version}
Copyright (C) 2018 Joe Jevnik
License GPLv2+: GNU GPL version 2 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.  Type "_license"
for details.""".format(version=version)


def run_phorth(stack_size=30000,
               memory=65535,
               *,
               stdlib=True,
               show_header=True):
    """Run a phorth session.

    Parameters
    ----------
    stack_size : int, optional
        The size of the stack to build in the phorth frame.
    memory : int, optional
        The size of the memory space for the phorth context. This translates
        to the size of the `co_code` of the context.
    stdlib : bool, optional
        Include ``stdlib.fs`` in the default vocabulary?
    show_header : bool, optional
        Print the license information at the start of the repl session.
    """
    here, ctx = build_phorth_ctx(
        stack_size,
        memory,
        word_impl=repl_word_impl(stdlib=stdlib),
    )
    # set a tracer to enable some features in PyFrame_EvalFrameEx
    old_trace = gettrace()
    settrace(_tracer)

    if show_header:
        print(_header)
    try:
        jump_handler(ctx(
            immediate=True,
            here=here,
            latest=None,
            cstack=[],
            stack_size=0,
            literals=[],
            tmp=None,
        ))
    except Done:
        return None
    finally:
        settrace(old_trace)  # reset the old tracer.
