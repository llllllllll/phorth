from functools import partial
import os.path as pth


class Done(Exception):
    """Exception type that marks that our phorth session is over.
    """


def repl_word_impl(*, stdlib):
    """Create the function that will read each word from stdin.

    Parameters
    ----------
    stdlib : bool
        Include ``stdlib.fs`` in the default vocabulary?

    Returns
    -------
    word_impl : callable[str]
        The implementation for the word word.

    Raises
    ------
    Done
        Raised when there are no more words to emit.
    """
    def read_words(*, input=input):
        if stdlib:
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
