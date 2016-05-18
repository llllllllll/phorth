from ast import literal_eval
from functools import partial
import os.path as pth
import pkg_resources
import readline  # noqa
import sys

from toolz import concatv
import toolz.curried.operator as op

from ._primitives import (  # noqa
    Word,
    append_lit,
    argnames,
    bcomma_impl,
    branch_impl,
    bread_impl,
    bwrite_impl,
    create_impl,
    clear_cstack,
    comma_impl,
    docol_impl,
    find_impl,
    lit_impl,
    pop_return_addr,
    print_stack_impl,
    push_return_addr,
    read_impl,
    write_impl,
)


class Done(Exception):
    """Exception type that marks that our phorth session is over.
    """


def make_word_impl():
    """Create the function that will read each word from stdin.

    Returns
    -------
    word_impl : callable[() -> str]
        The implementation for the word word.

    Raises
    ------
    Done
        Raised when there are no more words to emit.
    """
    def read_words(*, input=input):
        with open(pth.join(pth.dirname(__file__), 'stdlib.fs')) as f:
            for line in f:
                for word in line.split():
                    yield word.lower()

        try:
            while True:
                for word in input('> ').split():
                    yield word.lower()
        except (EOFError, KeyboardInterrupt):
            print()  # add a line so the outpue ends on a new line
            raise Done()

    return partial(next, read_words())


def process_lit(word,
                *,
                _literal_eval=literal_eval,
                _Exception=Exception,
                _NotImplemented=NotImplemented):
    """Implementation for the function that takes a word and checks if it
    is a literal.

    Parameters
    ----------
    word : str
        The word to parse.

    Returns
    -------
    maybe_lit : NotImplemented or constant
        Returns NotImplemented when ``word`` is not a literal, otherwise
        this returns the value of the literal.
    """
    try:
        return _literal_eval(word)
    except _Exception:
        return _NotImplemented


def handle_exception(exc,
                     *,
                     _Done=Done,
                     _type=type,
                     _getframe=sys._getframe,
                     _isinstance=isinstance,
                     _Word=Word,
                     _clear_cstack=clear_cstack):
    """Handle exceptions that are raised during phorth operations.

    Parameters
    ----------
    exc : Exception
        The exception that was raised.

    Notes
    -----
    This normally just prints the exception and restarts jumps us to the start
    of the repl with a clean stack. If ``exc`` is an instance of ``Done``, this
    will reraise the exception and kill the phorth session.
    """
    if _isinstance(exc, _Done):
        # reraise the sentinel `Done` type
        raise Done()

    f = _getframe(1)
    cstack = _clear_cstack(f)
    print(
        'traceback, most recent call last:\n  %s\n%s: %s' % (
            '\n  '.join(map(
                str,
                concatv(
                    map(op.add(1), reversed(cstack)),
                    (exc.__traceback__.tb_lasti,),
                ))),
            _type(exc).__name__,
            exc,
        ),
    )


def py_call_impl(f, *reversed_args):
    """Implementation for the py::call word that calls a python function from
    the stack.

    Parameters
    ----------
    f : callable
        The function to call.
    *reversed_args
        The arguments to apply to ``f`` in reverse order.

    Returns
    -------
    called : any
        The result of calling ``f`` with ``reversed_args`` in reverse order.
    """
    return f(*reversed(reversed_args))


def license_impl():
    """Print the license.
    """
    print(pkg_resources.resource_string(__name__, 'LICENSE').decode('ascii'))
