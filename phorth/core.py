from itertools import chain
import os.path as pth

from .builtins import builtins
from .exc import Underflow, UnknownWord
from .word import Lit


class Namespace(dict):
    def __getitem__(self, key):
        key = key.lower()
        try:
            return super().__getitem__(key)
        except KeyError:
            for f in (int, float):
                try:
                    return Lit(f(key))
                except ValueError:
                    pass

            raise

    @classmethod
    def builtins(cls):
        return cls(builtins)


class State:
    """The state of the forth interpreter.

    Parameters
    ----------
    words : iterable[str]
        The words to process.
    file : str, optional
        The starting file name.
    dstack : list[any], optional
        The starting data stack.
    cstack : list[any], optional
        The starting control stack.
    namespace : mapping[str -> Word]
        The starting namespace.
    use_stdlib : bool, optional
        Should the non-builtin standard library be loaded.
    """
    def __init__(self,
                 words,
                 file='<stdin>',
                 dstack=None,
                 cstack=None,
                 namespace=None,
                 use_stdlib=True):
        if use_stdlib:
            words = chain(
                (
                    ('import', -1, -1),
                    (pth.join(pth.dirname(__file__), 'stdlib.fs'), -1, -1),
                ),
                words,
            )

        self.words = words
        self.file = file
        self.lno = -1
        self.col = -1
        self.dstack = dstack = dstack or []
        self.push = dstack.append

        def pop(*, _pop=dstack.pop):
            try:
                return _pop()
            except IndexError:
                raise self.underflow_error()

        self.pop = pop
        self.peek = lambda *, _dstack=dstack: dstack[-1]
        self.cstack = cstack or []
        self.namespace = namespace or Namespace.builtins()
        self.use_stdlib = use_stdlib
        self.last_word = None
        self.addr = 0
        self._immediate_stack = 0
        self.last_doc = None

    def nextword(self):
        word, self.lno, self.col = next(self.words)
        return word

    def iterwords(self):
        for word, self.lno, self.col in self.words:
            yield word

    def underflow_error(self):
        return Underflow(self.file, self.lno, self.col)

    def lookup(self, name):
        try:
            return self.namespace[name]
        except KeyError:
            raise UnknownWord(name, self.file, self.lno, self.col)

    @property
    def immediate(self):
        return not self._immediate_stack

    def push_not_immediate(self):
        self._immediate_stack += 1

    def pop_not_immediate(self):
        self._immediate_stack -= 1
