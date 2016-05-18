from dis import dis
from functools import partial
from heapq import heappush
import operator as op
from pprint import pprint
import sys
from types import CodeType, FunctionType

from toolz import compose
from codetransformer import Code, instructions
from codetransformer.code import _sparse_args

from .primitives import (
    Done,
    Word,
    append_lit,
    argnames,
    bcomma_impl,
    branch_impl,
    bread_impl,
    bwrite_impl,
    create_impl,
    comma_impl,
    docol_impl,
    find_impl,
    handle_exception,
    lit_impl,
    make_word_impl,
    pop_return_addr,
    print_stack_impl,
    process_lit,
    push_return_addr,
    py_call_impl,
    read_impl,
    write_impl,
)


class UnknownWord(Exception):
    """Raised when find does not return a result in the dictionary.
    """


class NotAWord(Exception):
    """Raised when >cfa is used on an object that is not a word.
    """


_CMP = instructions.COMPARE_OP
_single_instr_words = {
    '^': instructions.BINARY_POWER,
    '*': instructions.BINARY_MULTIPLY,
    '/': instructions.BINARY_TRUE_DIVIDE,
    'mod': instructions.BINARY_MODULO,
    '+': instructions.BINARY_ADD,
    '-': instructions.BINARY_SUBTRACT,
    '<<': instructions.BINARY_LSHIFT,
    '>>': instructions.BINARY_RSHIFT,
    '&': instructions.BINARY_AND,
    'xor': instructions.BINARY_XOR,
    '|': instructions.BINARY_OR,
    'swap': instructions.ROT_TWO,
    'drop': instructions.POP_TOP,
    'dup': instructions.DUP_TOP,
    '2dup': instructions.DUP_TOP_TWO,
    'rot': instructions.ROT_THREE,
    'nop': instructions.NOP,
    '.': instructions.PRINT_EXPR,
    '=': partial(_CMP, _CMP.comparator.EQ),
    '>': partial(_CMP, _CMP.comparator.GT),
    '>=': partial(_CMP, _CMP.comparator.GE),
    '<>': partial(_CMP, _CMP.comparator.NE),
    '<': partial(_CMP, _CMP.comparator.LT),
    '<=': partial(_CMP, _CMP.comparator.LE),
    'true': partial(instructions.LOAD_CONST, True),
    'false': partial(instructions.LOAD_CONST, False),
    'none': partial(instructions.LOAD_CONST, None),
    'here': partial(instructions.LOAD_FAST, 'here'),
    'latest': partial(instructions.LOAD_FAST, 'latest'),
    '_cstack': partial(instructions.LOAD_FAST, 'cstack'),
}
if hasattr(instructions, 'BINARY_MATRIX_MULTIPLY'):
    _single_instr_words['matmul'] = instructions.BINARY_MATRIX_MULTIPLY


def build_phorth_ctx(stack_size, memory):
    """Create a phorth context with the given stack size and memory.

    This context will have only the primitive words defined but is ready for
    bootstrapping.

    Parameters
    ----------
    stack_size : int
        The size of the stack to build in the phorth frame.
    memory : int
        The size of the memory space for the phorth context. This translates
        to the size of the `co_code`.

    Returns
    -------
    here : int
        The first free memory address in ``ctx``.
    ctx : Context
        The phorth context object, this is a generator that must be consumed
        by `run_phorth` because the bytecode is non-standard.
    """
    word_instrs = {}
    order = []
    default_priority = 10
    is_immediate = {}

    def builtin(name=None, immediate=False, priority=None):
        def _(f):
            nonlocal name
            nonlocal priority
            nonlocal default_priority

            if name is None:
                name = f.__name__

            word_instrs[name] = tuple(f())
            is_immediate[name] = immediate

            if priority is None:
                priority = default_priority
                # leave 10 slots to weave new functions between functions that
                # don't really care about order
                default_priority += 10
            heappush(order, (priority, name))
            return f

        return _

    # build the vocab
    vocab = {}
    instrs = []
    here = 0

    def _compile_vocab():
        nonlocal here

        for _, name in order:
            vocab[name] = Word(
                name,
                len(list(_sparse_args(instrs))),
                is_immediate[name],
            )
            instrs.extend(word_instrs[name])

        order[:] = []
        here = len(list(_sparse_args(instrs)))

    @builtin()
    def __next():
        # pop the return address from the cstack and yield the new address
        # to jump to
        yield instructions.LOAD_CONST(pop_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.YIELD_VALUE()

    def next_instruction():
        """Create a new instruction that will exit using the control stack.
        """
        return instructions.JUMP_ABSOLUTE(word_instrs['__next'][0])

    def sync_frame():
        """Sync the frame object with some local variables in
        PyEval_EvalFrameEx. This needs to happend before using any primitive
        function that cares about the instruction pointer or the stacksize.
        """
        # our custom runner understands that `yield None` means 'do not jump
        # anywhere, just sync the frame and continue
        yield instructions.LOAD_CONST(None)
        yield instructions.YIELD_VALUE()

    def _debug_print():
        """DUP_TOP() and PRINT_EXPR()

        Used for debugging the bytecode by providing a "print statment" like
        feature in the bytecode.
        """
        yield instructions.DUP_TOP()
        yield instructions.PRINT_EXPR()

    def _word(word_impl=make_word_impl()):
        yield instructions.LOAD_CONST(word_impl)
        yield instructions.CALL_FUNCTION(0)

    @builtin()
    def word():
        yield from _word()
        yield next_instruction()

    @builtin()
    def find():
        yield instructions.LOAD_CONST(find_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield next_instruction()

    def _nip():
        yield instructions.ROT_TWO()
        yield instructions.POP_TOP()

    @builtin(name='>cfa')
    def pushcfa():
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(Word)
        yield instructions.LOAD_CONST(isinstance)
        yield instructions.ROT_THREE()
        yield instructions.CALL_FUNCTION(2)

        not_word_instr = instructions.LOAD_CONST(NotAWord)
        yield instructions.POP_JUMP_IF_FALSE(not_word_instr)

        yield instructions.LOAD_ATTR('addr')
        yield next_instruction()

        yield not_word_instr
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.RAISE_VARARGS(1)

    @builtin(name=',')
    def comma():
        yield instructions.LOAD_CONST(comma_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('here')
        yield next_instruction()

    @builtin(name='b,')
    def bcomma():
        yield instructions.LOAD_CONST(bcomma_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('here')
        yield next_instruction()

    def write_byte(b):
        yield instructions.LOAD_CONST(b)
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['b,'][0])

    def write_short(s):
        yield instructions.LOAD_CONST(s)
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs[','][0])

    def inline_write_byte(b):
        yield instructions.LOAD_CONST(bcomma_impl)
        yield instructions.LOAD_CONST(b)
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('here')

    def inline_write_short_from_stack():
        yield instructions.LOAD_CONST(comma_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('here')

    def inline_write_short(s):
        yield instructions.LOAD_CONST(comma_impl)
        yield instructions.LOAD_CONST(s)
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('here')

    handle_exception_instr = instructions.POP_TOP()
    setup_except_instr = instructions.SETUP_EXCEPT(handle_exception_instr)

    def __start(*, counting_run=False):
        yield setup_except_instr
        first = instructions.LOAD_CONST(push_return_addr)
        yield first
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['word'][0])
        # We need to duplicate the word on the stack for proper error handling
        # later.
        # We dup it twice giving us 3 copies on the stack for:
        #   find
        #   literal lookup
        #   unknown word error
        yield instructions.DUP_TOP()
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['find'][0])
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(None)
        yield instructions.COMPARE_OP.IS

        process_lit_instr = instructions.POP_TOP()
        yield instructions.POP_JUMP_IF_TRUE(process_lit_instr)

        # clear the word strings from the stack
        yield instructions.ROT_THREE()
        yield instructions.POP_TOP()
        yield instructions.POP_TOP()
        yield instructions.DUP_TOP()
        yield instructions.LOAD_ATTR('addr')
        yield instructions.LOAD_CONST(1)
        yield instructions.BINARY_SUBTRACT()
        yield instructions.LOAD_FAST('immediate')

        immediate_with_nip_instr = instructions.ROT_TWO()
        yield instructions.POP_JUMP_IF_TRUE(immediate_with_nip_instr)

        yield instructions.ROT_TWO()
        yield instructions.LOAD_ATTR('immediate')

        immediate_instr = instructions.LOAD_CONST(push_return_addr)
        yield instructions.POP_JUMP_IF_TRUE(immediate_instr)

        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs[','][0])
        yield instructions.JUMP_ABSOLUTE(first)

        yield immediate_with_nip_instr
        yield instructions.POP_TOP()
        yield immediate_instr
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.YIELD_VALUE()
        # We need to add some padding so that the return adress gets
        # computed correctly. Maybe we should have two functions like:
        # push_return_jmp_addr/push_return_yield_addr to handle this.
        yield instructions.NOP()
        yield instructions.NOP()
        yield instructions.JUMP_ABSOLUTE(first)

        yield process_lit_instr
        yield instructions.LOAD_CONST(process_lit)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(NotImplemented)
        yield instructions.COMPARE_OP.IS

        unknown_word_instr = instructions.POP_TOP()
        yield instructions.POP_JUMP_IF_TRUE(unknown_word_instr)
        # clear the word string left for the unknown word case
        yield from _nip()
        yield instructions.LOAD_FAST('immediate')
        yield instructions.POP_JUMP_IF_TRUE(first)

        yield instructions.LOAD_CONST(append_lit)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield from inline_write_short(
            None
            if counting_run else
            len(list(_sparse_args(__start(counting_run=True)))) - 1,
        )
        yield from inline_write_short_from_stack()
        yield instructions.JUMP_ABSOLUTE(first)

        yield unknown_word_instr
        yield instructions.LOAD_CONST(UnknownWord)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.RAISE_VARARGS(1)

        # this is the bytecode side of the literal implementation which
        # appears to be dead code but does get jumped to
        if counting_run:
            return

        yield instructions.LOAD_CONST(lit_impl)
        yield instructions.LOAD_CONST(pop_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.CALL_FUNCTION(1)
        yield instructions.UNPACK_SEQUENCE(2)
        yield instructions.YIELD_VALUE()

    # this segment goes first, it handles the input loop
    # this is not a decorator because it is recurisive to count the addr
    # of lit
    builtin(priority=0)(__start)

    @builtin()
    def __docol():
        yield instructions.LOAD_CONST(docol_impl)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.YIELD_VALUE()

    @builtin()
    def _dis():
        yield instructions.LOAD_CONST(dis)
        yield instructions.LOAD_CONST(sys._getframe)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.LOAD_ATTR('f_code')
        yield instructions.CALL_FUNCTION(1)
        yield instructions.POP_TOP()
        yield next_instruction()

    @builtin()
    def words():
        yield instructions.LOAD_CONST(compose(
            pprint,
            partial(sorted, key=op.attrgetter('name')),
            dict.values,
        ))
        yield instructions.LOAD_CONST(globals)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.CALL_FUNCTION(1)
        yield instructions.POP_TOP()
        yield next_instruction()

    @builtin()
    def create():
        yield instructions.LOAD_CONST(create_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.STORE_FAST('latest')
        yield next_instruction()

    @builtin(name='[')
    def lbracket():
        yield instructions.LOAD_CONST(False)
        yield instructions.STORE_FAST('immediate')
        yield next_instruction()

    @builtin(name=']', immediate=True)
    def rbracket():
        yield instructions.LOAD_CONST(True)
        yield instructions.STORE_FAST('immediate')
        yield next_instruction()

    @builtin(name="'")
    def quote():
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['word'][0])
        # We need to duplicate the word on the stack for proper error handling
        # later.
        # We dup it once giving us 2 copies on the stack for:
        #   find
        #   unknown word error
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['find'][0])
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(None)
        yield instructions.COMPARE_OP.IS

        unknown_word_instr = instructions.POP_TOP()
        yield instructions.POP_JUMP_IF_TRUE(unknown_word_instr)

        # clear the word strings from the stack
        yield from _nip()
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['>cfa'][0])
        yield next_instruction()

        yield instructions.POP_JUMP_IF_TRUE(unknown_word_instr)
        # clear the word string left for the unknown word case
        yield from _nip()
        yield next_instruction()

        yield unknown_word_instr
        yield instructions.LOAD_CONST(UnknownWord)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.RAISE_VARARGS(1)

    @builtin(name='@')
    def read():
        yield instructions.LOAD_CONST(read_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield next_instruction()

    @builtin(name='b@')
    def bread():
        yield instructions.LOAD_CONST(bread_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield next_instruction()

    @builtin(name='!')
    def write():
        yield instructions.LOAD_CONST(write_impl)
        yield instructions.ROT_THREE()
        yield instructions.CALL_FUNCTION(2)
        yield instructions.POP_TOP()
        yield next_instruction()

    @builtin(name='b!')
    def bwrite():
        yield instructions.LOAD_CONST(bwrite_impl)
        yield instructions.ROT_THREE()
        yield instructions.CALL_FUNCTION(2)
        yield instructions.POP_TOP()
        yield next_instruction()

    @builtin()
    def over():
        yield instructions.ROT_TWO()
        yield instructions.DUP_TOP()
        yield instructions.ROT_THREE()
        yield next_instruction()

    @builtin(immediate=True)
    def branch():
        yield instructions.LOAD_CONST(branch_impl)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION()
        yield instructions.YIELD_VALUE()

    @builtin(name='0branch', immediate=True)
    def zerobranch():
        yield instructions.LOAD_CONST(0)
        yield instructions.COMPARE_OP.EQ
        yield instructions.POP_JUMP_IF_TRUE(word_instrs['branch'][0])
        yield instructions.YIELD_VALUE()

    @builtin(name='.s')
    def print_stack():
        yield from sync_frame()  # syncing because we want the stacksize
        yield instructions.LOAD_CONST(print_stack_impl)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield next_instruction()

    @builtin('/mod')
    def _divmod():
        yield instructions.LOAD_CONST(divmod)
        yield instructions.ROT_THREE()
        yield instructions.CALL_FUNCTION()
        yield next_instruction()

    @builtin()
    def bye():
        yield instructions.LOAD_CONST(Done())
        yield instructions.RAISE_VARARGS(1)

    @builtin()
    def nip():
        yield from _nip()
        yield next_instruction()

    for name, instr in _single_instr_words.items():
        # build all the words that are one CPython instruction
        @builtin(name=name)
        def _(instr=instr):
            yield instr()
            yield next_instruction()

    _compile_vocab()

    @builtin(name=':')
    def colon():
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['word'][0])
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['create'][0])
        yield from write_byte(instructions.LOAD_CONST.opcode)
        yield from write_short(0)  # push_return_addr
        yield from write_byte(instructions.CALL_FUNCTION.opcode)
        yield from write_short(0)
        yield from write_byte(instructions.POP_TOP.opcode)
        yield from write_byte(instructions.JUMP_ABSOLUTE.opcode)
        yield from write_short(vocab['__docol'].addr)
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs['['][0])
        yield next_instruction()

    @builtin()
    def exit():
        yield instructions.LOAD_CONST(pop_return_addr)
        yield instructions.CALL_FUNCTION(0)
        yield instructions.POP_TOP()
        yield next_instruction()

    _compile_vocab()

    @builtin(name=';', immediate=True)
    def semicolon():
        yield from write_short(vocab['exit'].addr - 1)
        yield instructions.LOAD_CONST(push_return_addr)
        yield instructions.CALL_FUNCTION()
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(word_instrs[']'][0])
        yield next_instruction()

    @builtin()
    def immediate():
        yield instructions.LOAD_CONST(True)
        yield instructions.LOAD_FAST('latest')
        yield instructions.STORE_ATTR('immediate')
        yield next_instruction()

    @builtin(name='(', immediate=True)
    def lparen():
        loop = instructions.LOAD_CONST(')')
        yield loop
        yield from _word()
        yield instructions.COMPARE_OP.EQ
        yield instructions.POP_JUMP_IF_FALSE(loop)
        yield next_instruction()

    @builtin(name='py::import')
    def py_import():
        yield instructions.LOAD_CONST(__import__)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield next_instruction()

    @builtin(name='py::getattr')
    def py_getattr():
        yield instructions.LOAD_CONST(getattr)
        yield instructions.ROT_THREE()
        yield instructions.CALL_FUNCTION(2)
        yield next_instruction()

    def _nrot():
        yield instructions.ROT_THREE()
        yield instructions.ROT_THREE()

    @builtin(name='py::call')
    def py_call():
        start = instructions.BUILD_LIST(0)

        # validate that nargs is >= 0 to avoid infinite loop
        yield instructions.DUP_TOP()
        yield instructions.LOAD_CONST(0)
        yield instructions.COMPARE_OP.LT
        yield instructions.POP_JUMP_IF_FALSE(start)
        yield instructions.LOAD_CONST('nargs must be >= 0; got %s')
        yield instructions.ROT_TWO()
        yield instructions.BINARY_MODULO()
        yield instructions.LOAD_CONST(ValueError)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.RAISE_VARARGS(1)

        # create a list to hold the function and arguments; append the function
        # first
        yield start
        yield from _nrot()
        yield instructions.LIST_APPEND(1)
        yield instructions.STORE_FAST('tmp')

        # use the nargs as a counter; append elements until nargs == 0
        loop = instructions.DUP_TOP()
        yield loop
        yield instructions.LOAD_CONST(0)
        yield instructions.COMPARE_OP.EQ

        call_impl = instructions.POP_TOP()
        yield instructions.POP_JUMP_IF_TRUE(call_impl)

        yield instructions.LOAD_CONST(1)
        yield instructions.ROT_TWO()
        yield instructions.BINARY_SUBTRACT()
        yield instructions.LOAD_FAST('tmp')
        yield from _nrot()
        yield instructions.LIST_APPEND(1)
        yield instructions.POP_TOP()
        yield instructions.JUMP_ABSOLUTE(loop)

        # *unpack the argument list into `py_call_impl`
        yield call_impl
        yield instructions.LOAD_CONST(py_call_impl)
        yield instructions.LOAD_FAST('tmp')
        yield instructions.CALL_FUNCTION_VAR(0)
        yield next_instruction()

    _compile_vocab()

    def _tail():
        for _ in range(memory - len(list(_sparse_args(instrs))) - 15):
            yield instructions.NOP()
        yield handle_exception_instr
        yield from _nip()
        yield instructions.LOAD_CONST(handle_exception)
        yield instructions.ROT_TWO()
        yield instructions.CALL_FUNCTION(1)
        yield instructions.POP_TOP()
        yield instructions.POP_EXCEPT()
        yield instructions.JUMP_ABSOLUTE(setup_except_instr)

    instrs.extend(_tail())

    code = Code(
        instrs,
        argnames=argnames,
        new_locals=True,
    ).to_pycode()
    return here, FunctionType(
        CodeType(
            len(argnames),
            0,
            len(argnames),
            stack_size,
            code.co_flags,
            code.co_code,
            tuple(map(_coerce_false_and_true, code.co_consts)),
            code.co_names,
            code.co_varnames,
            '<phorth>',
            '<phorth>',
            1,
            b'',
            (),
            (),
        ),
        {k: v for k, v in vocab.items() if not k.startswith('__')},
    )


def _coerce_false_and_true(n):
    """When deduping the co_consts in codetransformer we use an `in` check
    which currently  folds True and False with 1 and 0 respectivly.
    This causes the ``immediate`` word to fail because it is setting a
    ``T_BOOL`` field to an int.
    """
    if n == 0:
        return False
    if n == 1:
        return True
    return n
