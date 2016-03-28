from contextlib import ExitStack
import operator as op
import re
import sys

try:
    import readline  # noqa
except ImportError:
    pass


_splitwords = re.compile(r'\S+').finditer


def words(file=None):
    """Read words from a file or stdin.

    Parameters
    ----------
    file : file-like object, optional
        The open file to read from. If this is None, we will read from
        sys.stdin.
    """
    lno = 1
    with ExitStack() as stack:
        if file is not None:
            old = sys.stdin
            prompt = ''
            sys.stdin = file

            @stack.callback
            def _c():
                sys.stdin = old
        else:
            prompt = '> '

        while True:
            try:
                line = input(prompt)
            except EOFError:
                break

            it = _splitwords(line)
            for match in it:
                word = match.group()
                if word == '\\':
                    # handle line comments
                    for _ in it:
                        pass
                    continue
                yield word, lno, match.start()
            lno += 1


class Word:
    """A forth word.

    Parameters
    ----------
    name : str
        The name of this word.
    code : callable
        The code to execute for this word.
    immediate : bool, optional
        Should this word be executed immediatly even when not in immediate
        mode.
    """
    def __init__(self, name, code, immediate=False):
        self.name = name
        self.code = code
        self.immediate = immediate

    def __repr__(self):
        return '<Word %r: immediate=%s>' % (self.name, self.immediate)


class Lit(Word):
    """A literal or constant.

    Parameters
    ----------
    lit : any
        The literal to push.
    name : str
        The name of the literal, this is used when created with ``constant``.
    """
    def __init__(self, lit, name=None):
        def code(st, *, _lit=lit):
            st.push(_lit)
            st.addr += 1

        super().__init__(
            repr(lit) if name is None else name,
            code,
            immediate=False,
        )
        self.lit = lit

    def __repr__(self):
        return '<Lit: %r>' % self.lit


class Code:
    """The code for a word defined in forth.

    Parameters
    ----------
    name : str
        The name of the word this is the code forth.
    words : tuple[Word]
        The words that make up this code.
    doc : str, optional
        The docstring for the word.
    """
    def __init__(self, name, words, doc=None):
        self.name = self.__name__ = name
        self.words = words = tuple(words)
        self.code = tuple(map(op.attrgetter('code'), reversed(words)))
        self.doc = doc

    def __call__(self, st):
        code = self.code
        codelen = len(code)
        st.addr = 0
        while 0 <= st.addr < codelen:
            code[st.addr](st)
