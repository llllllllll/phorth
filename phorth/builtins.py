from functools import wraps
import operator as op
from pprint import pprint
from types import MappingProxyType

from .word import Word, Code, Lit, words
from .exc import InvalidWordUsage


_builtins = {
    'true': Lit(True, 'true'),
    'false': Lit(False, 'false'),
}
builtins = MappingProxyType(_builtins)


def builtin(immediate=False, name=None, increment_addr=True):
    """Mark that a function is a builtin.

    Parameters
    ----------
    immediate : bool, optional
        Is this word immediate?
    name : str, optional
        The name of this word. Defaults to ``f.__name__``.
    """
    def _(f):
        if increment_addr:
            @wraps(f)
            def f(st, _f=f):
                _f(st)
                st.addr += 1

        nonlocal name
        if name is None:
            name = f.__name__
        _builtins[name] = Word(name, f, immediate=immediate)
        return f

    return _


def unary_func(f, doc=None):
    """Wrapper for a unary python function that passes the top element
    of the stack and pushes the return to the stack.

    Parameters
    ----------
    f : callable[any -> any]
        The function to wrap.
    doc : str, optional
        The docstring to use, default: ( n1 n2 -- n2 ).
    """
    def _(st):
        """( n1 -- n2 )
        """
        st.push(f(st.pop()))
    _.__name__ = f.__name__
    if doc is not None:
        _.__doc__ = doc.strip()
    return _


def binary_func(f, doc=None):
    """Wrapper for a binary python function that passes the top two elements of
    the stack in the order they appear and pushes the return to the stack.

    Parameters
    ----------
    f : callable[(any, any) -> any]
        The function to wrap.
    doc : str, optional
        The docstring to use, default: ( n1 n2 -- n3 ).
    """
    def _(st):
        """( n1 n2 -- n3 )
        """
        b, a = st.pop(), st.pop()
        st.push(f(a, b))
    _.__name__ = f.__name__
    if doc is not None:
        _.__doc__ = doc.strip()
    return _


def ternary_func(f, doc=None):
    """Wrapper for a binary function that passes the top three elements of
    the stack of the otder they appear and pushes the return to the stack.

    Parameters
    ----------
    f : callable[(any, any, any) -> any]
        The function to wrap.
    doc : str, optional
        The docstring to use, default: ( n1 n2 n3 -- n4 ).
    """
    def _(st):
        """( n1 n2 n3 -- n4 )
        """
        c, b, a = st.pop(), st.pop(), st.pop()
        st.push(f(a, b, c))
    _.__name__ = f.__name__
    if doc is not None:
        _.__doc__ = doc
    return _


@builtin(name='.')
def print_top(st):
    """( n -- )
    """
    print(st.pop())


@builtin(name='.s')
def print_stack(st):
    """( -- )
    """
    dstack = st.dstack
    print('<%d>' % len(dstack), ' '.join(map(repr, dstack)))


@builtin(name='words')
def words_(st):
    """( -- )
    """
    pprint({name: _see(word) for name, word in st.namespace.items()})


@builtin()
def dup(st):
    """( n -- n n )
    """
    st.push(st.peek())


@builtin()
def drop(st):
    """( n -- )
    """
    st.pop()


@builtin()
def swap(st):
    """( n1 n2 -- n2 n1 )
    """
    dstack = st.dstack
    try:
        dstack[-2], dstack[-1] = dstack[-1], dstack[-2]
    except IndexError:
        raise st.underflow_error()


@builtin(name='2swap')
def twoswap(st):
    """( n1 n2 n3 n4 -- n3 n4 n1 n2 )
    """
    dstack = st.dstack
    try:
        dstack[-3], dstack[-4], dstack[-1], dstack[-2] = (
            dstack[-1],
            dstack[-2],
            dstack[-3],
            dstack[-4],
        )
    except IndexError:
        raise st.underflow_error()


@builtin()
def over(st):
    """( n1 n2 -- n2 n1 n2 )
    """
    st.push(st.dstack[-2])


@builtin()
def rot(st):
    """( n1 n2 n3 -- n2 n3 n1 )
    """
    dstack = st.dstack
    try:
        dstack[-2], dstack[-3], dstack[-1] = (
            dstack[-1],
            dstack[-2],
            dstack[-3],
        )
    except IndexError:
        raise st.underflow_error()


@builtin(name='-rot')
def rrot(st):
    """( n1 n2 n3 -- n3 n1 n2 )
    """
    dstack = st.dstack
    try:
        dstack[-3], dstack[-1], dstack[-2] = (
            dstack[-1],
            dstack[-2],
            dstack[-3],
        )
    except IndexError:
        raise st.underflow_error()


@builtin(name='[', immediate=True)
def lbracket(st):
    st.cstack.append('[')
    st.push_not_immediate()


@builtin(name=']', immediate=True)
def rbracket(st):
    try:
        name = st.cstack.pop()
        if name != '[':
            raise IndexError()
    except IndexError:
        raise InvalidWordUsage(
            ']',
            st.file,
            st.lno,
            st.col,
            "']' used without a matching '['",
        )
    st.pop_not_immediate()


@builtin(name='(', immediate=True)
def lparen(st):
    st.cstack.append(('(', len(st.dstack)))
    lbracket(st)


@builtin(name=')', immediate=True)
def rparen(st):
    rbracket(st)
    cstack = st.cstack
    try:
        word, start_idx = cstack.pop()
        if word != '(':
            raise ValueError()
    except (ValueError, IndexError):
        raise InvalidWordUsage(
            ')',
            st.file,
            st.lno,
            st.col,
            "')' used without a matching '('",
        )

    dstack = st.dstack
    st.last_doc = '( %s )' % ' '.join(dstack[start_idx:])
    dstack[:] = dstack[:start_idx]


@builtin(name=':')
def colon(st):
    name = st.nextword()
    st.cstack.append((':', name, len(st.dstack)))
    lbracket(st)
    st.last_doc = None


@builtin(name=';', immediate=True)
def semicolon(st):
    rbracket(st)
    try:
        word, name, start_idx = st.cstack.pop()
        if word != ':':
            raise ValueError()
    except (ValueError, IndexError):
        raise InvalidWordUsage(
            ';',
            st.file,
            st.lno,
            st.col,
            "';' used without a matching ':'",
        )

    dstack = st.dstack
    st.namespace[name] = st.last_word = Word(
        name,
        Code(name, map(st.lookup, reversed(dstack[start_idx:])), st.last_doc),
    )
    dstack[:] = dstack[:start_idx]


@builtin()
def immediate(st):
    st.last_word.immediate = True


@builtin(name="'", immediate=True)
def quote(st):
    st.push(st.nextword())


@builtin()
def depth(st):
    """( -- n )
    """
    st.push(len(st.dstack))


@builtin(name='@')
def read(st):
    """( n -- n )
    """
    st.push(st.dstack[st.pop()])


@builtin(name='!')
def write(st):
    """( n1 n2 -- )
    """
    dstack = st.dstack
    dstack[st.pop()] = st.pop()


def _see_code(c):
    if isinstance(c, Lit):
        return repr(c.lit)
    if isinstance(c, Word):
        return c.name
    return '<builtin: %s%s>' % (
        c.__name__,
        (' %s' % c.__doc__.strip()) if c.__doc__ is not None else '',
    )


def _see(word):
    if isinstance(word, Lit):
        return repr(word.lit)
    code = word.code
    if isinstance(code, Code):
        doc = code.doc
        return ': %s%s%s ;' % (
            code.name,
            (' %s ' % doc) if doc is not None else '',
            ' '.join(map(_see_code, reversed(code.words))),
        )

    return _see_code(code)


@builtin(immediate=True)
def see(st):
    print(_see(st.lookup(st.nextword())))


@builtin(name='import', immediate=True)
def import_(st):
    from .__main__ import run_phorth

    name = st.nextword()
    old_line = st.lno
    old_file = st.file
    st.file = name
    old_words = st.words
    with open(name) as f:
        st.words = words(f)
        run_phorth(st)
    st.words = old_words
    st.file = old_file
    st.lno = old_line


@builtin()
def bye(st):
    exit()


@builtin()
def clear(st):
    """( -- )
    """
    st.dstack[:] = []


@builtin(immediate=True)
def constant(st):
    name = st.nextword()
    st.namespace[name] = Lit(st.pop(), name=name)


@builtin(name='if')
def if_(st):
    condition = st.pop()
    if not condition:
        lparen(st)
    st.cstack.append(('if', condition))


@builtin(immediate=True)
def then(st):
    try:
        name, condition = st.cstack.pop()
    except (ValueError, IndexError):
        raise InvalidWordUsage(
            'then',
            st.file,
            st.lno,
            st.col,
            "'then' used without a matching 'if'",
        )

    if not condition:
        rparen(st)


@builtin()
def jmp(st):
    st.addr = st.pop()


@builtin(name='and')
@binary_func
def and_(a, b):
    return a and b


@builtin(name='or')
@binary_func
def or_(a, b):
    return a or b


@builtin()
@ternary_func
def between(n, min, max):
    return min <= n <= max


_cmp_doc = '( n1 n2 -- f )'
_pred_doc = '( n -- f )'


for name, f in {'!=': binary_func(op.ne, _cmp_doc),
                '&': binary_func(op.and_),
                '*': binary_func(op.mul),
                '**': binary_func(pow),
                '**mod': ternary_func(pow),
                '+': binary_func(op.add),
                '-': binary_func(op.sub),
                '/': binary_func(op.truediv),
                '<': binary_func(op.lt, _cmp_doc),
                '<<': binary_func(op.lshift),
                '<=': binary_func(op.le, _cmp_doc),
                '=': binary_func(op.eq, _cmp_doc),
                '>': binary_func(op.gt, _cmp_doc),
                '>>': binary_func(op.rshift),
                '>=': binary_func(op.ge, _cmp_doc),
                '^': binary_func(op.xor),
                'max': binary_func(max),
                'min': binary_func(min),
                'mod': binary_func(op.mod),
                '/mod': ternary_func(divmod),
                'abs': unary_func(abs),
                'bool': unary_func(bool, _pred_doc),
                'invert': unary_func(op.invert),
                'negate': unary_func(op.neg),
                'not': unary_func(op.not_, _pred_doc),
                'positive': unary_func(op.pos),
                '|': binary_func(op.or_)}.items():
    builtin(name=name)(f)

del op
del f
