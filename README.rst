==========
``phorth``
==========

``phorth`` is a bootstrapped forth-like language where instead of writing our
primitive words in some assembler, we have chosen to write them in a mix of
CPython bytecode and C++*. By using a superset of CPython bytecode, we may
interpret our ``phorth`` programs with an unmodified version of CPython using
the same interpreter loop that handles normal python code objects.

\* C++ is used where the VM is too restrictive. This is mainly used to handle
dynamic jumps which there is no opcode for in CPython.

Purpose
-------

``phorth`` exists because I wanted to attempt to use the CPython virtual machine
for a language that was not Python. Forth seemed like a decent candidate because
of the stack based nature of the VM; however, the CPython machine's model is
radically different which led to a lot of fun hacks later.

Model
-----

``phorth`` is designed to run inside of a single self modifying CPython code
object. The CPython data stack is not global, instead a new data stack is
created for each code object that is being executed. This means that there is no
simple way to write words like ``nip`` or ``over`` as Python function because
they just do stack manipulation. To get around this problem, I decided to make a
``phorth`` 'context' a single code object. This means that ``phorth`` gets a
single data stack to be managed by the interpreter. I can also take advantage of
all of CPython instructions that work on the stack. This means that ``nip`` can
be defined in terms of CPython instructions as ``ROT_TWO``, ``POP_TOP``. Some
words can even be implemented as single CPython instructions, for example:
``drop`` is just ``POP_TOP``!

Because I am not using CPython's control stack, this is implemented as a list
stored as a local variable of the frame. The local is accessed through two
functions ``push_return_addr`` and ``pop_return_addr`` which may only be called
from a ``phorth`` context. These function inspect the calling stack frame and
manipulate the values as needed.

Hacks
-----

Some terrible things needed to happen to make this work. The whole project is
hacks that are threaded together to do something cute, but below I will list
some of my favorites.

Mutation of Code Objects In Place During Runtime
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Probably the most terrible of all of the hacks is that I needed to be able to
mutate the code object as it was running. This is because I treat the
``co_code``, which is a ``bytes`` object, as a large mutable memory segment
which acts as the ``phorth`` context's addressable memory space. In Python there
is no way to mutate ``bytes``, which is good because they are supposed to be
immutable; (un)fortunatly there are no such restrictions in the CPython C API.

This allows us to define new words at runtime which is critical for a
Forth. Forth is very deeply tied to the repl and interactive experience so we
needed some way to define words on the fly.

Computed Jumps in the CPython VM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CPython has no need for a computed jump instruction so the VM does not have
one. This is totally reasonable for Python because, obviously, Python can
compiled in such a way that a computed goto is not needed. In ``phorth``, I
don't have as much static information so I needed to be able to jump to an
address in the code object dynamically. To implement this the ``phorth`` context
is actually a generator. This means that the code object has the
``CO_GENERATOR`` flag set and uses ``YIELD_VALUE`` instructions to pause control
flow. The ``phorth`` context is yields ``int``\* objects which are one less than
the address to jump to. The reason it is one less that the address to jump to is
that it really works by setting ``context.gi_frame.f_lasti`` (in C++ again, this
is not mutable in Python) to the value yielded. This means that when execution
resumes, it will resume at the new location. I decided to yield the ``lasti``
instead of the actual target because in most places the location is computed as
an offset from the current instruction pointer meaning I could subtract one from
the offset there and save another subtraction in the runner. I didn't want to
have all of my jump targets start with a ``POP_TOP`` so using the normal
generator ``next`` code would not work. The runner reimplements most of the
``next`` function with special handling to manage the ``lasti`` assignment and
reenter the code without pushing any values onto the stack.

\* There is a special case of yielding ``None`` which means resume execution on
the next instruction. For control flow this is a ``NOP``; however, yielding
causes the state of the ``gi_frame`` object to get synced with the internal
state of ``PyEval_EvalFrameEx``. This is needed to access the ``f_stacktop``
inside some of the primitive ``phorth`` words defined in C++.

Direct Threaded Code in CPython Bytecode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Direct threaded code is a model where functions are layed out as a list of
addresses of other functions, starting with a call to some machinery that starts
executing the thread. All functions need to end in some ``next`` function that
will jump to the next function in the thread.

There is a little more complexity to the computed jump machinery described
above. The context may yield a negative number which says, "derefence the
absolute value yielded and jump there, also decrement the value by 2 and push it
onto the control stack". This instruction is pretty complicated but it is
designed to make the direct threaded code model simpler. The ``docol`` procedure
starts the threading by yielding the inverse of the next instruction. This will
be seen by the runner which will dereference the value, jumping to the function
whose address appeared after the docol. It will also push ``addr - 2``, or
really the next word's address onto the control stack. Each word defined in
``phorth`` also ends in some ``exit`` procedure which just pops the top value
off the control stack and throws it away because it points to the address after
the function ends, afterwards it yields the top value of the control stack like
normal. This is basically using the control stack as a stack of instruction
pointers for each thread.

One side effect of this is that the ``co_code`` is really a superset of the
CPython bytecode because there are a lot of bytes that are not valid
instructions. This means that ``dis`` of the ``phorth`` context will often fail
once some words are defined.

Defined Words
-------------

Out of the box phorth comes with many words defined. The names are mostly taken
from forth with many omitted and some added. This list is nowhere near the list
of words required to be a compliant forth, but ``phorth`` is not aiming for
that. Like Python, words that start with ``_`` are pseudo private, or meant for
debugging. This includes ``_dis`` which prints the output of ``dis`` on the
``phorth`` context and ``_cstack`` which prints the control (return) stack.

Words starting with ``py::`` are meant to help interface with the CPython
virtual machine. For example, ``py::getattr`` pops a string and an object from
the stack and calls ``getattr``.

.. code-block::

   > words
   [<Word '!': addr=412, immediate=False>,
    <Word '&': addr=585, immediate=False>,
    <Word "'": addr=327, immediate=False>,
    <Word '(': addr=813, immediate=True>,
    <Word '*': addr=637, immediate=False>,
    <Word '+': addr=541, immediate=False>,
    <Word ',': addr=218, immediate=False>,
    <Word '-': addr=559, immediate=False>,
    <Word '-rot': addr=1133, immediate=False>,
    <Word '.': addr=509, immediate=False>,
    <Word '.s': addr=458, immediate=False>,
    <Word '/': addr=623, immediate=False>,
    <Word '/mod': addr=472, immediate=False>,
    <Word '0<': addr=927, immediate=False>,
    <Word '0=': addr=945, immediate=False>,
    <Word '0>': addr=963, immediate=False>,
    <Word '0branch': addr=448, immediate=True>,
    <Word '1+': addr=981, immediate=False>,
    <Word '1-': addr=999, immediate=False>,
    <Word '2*': addr=1017, immediate=False>,
    <Word '2+': addr=1035, immediate=False>,
    <Word '2-': addr=1053, immediate=False>,
    <Word '2/': addr=1071, immediate=False>,
    <Word '2drop': addr=1089, immediate=False>,
    <Word '2dup': addr=551, immediate=False>,
    <Word ':': addr=641, immediate=False>,
    <Word ';': addr=775, immediate=True>,
    <Word '<': addr=535, immediate=False>,
    <Word '<<': addr=563, immediate=False>,
    <Word '<=': addr=545, immediate=False>,
    <Word '<>': addr=529, immediate=False>,
    <Word '=': addr=519, immediate=False>,
    <Word '>': addr=627, immediate=False>,
    <Word '>=': addr=605, immediate=False>,
    <Word '>>': addr=615, immediate=False>,
    <Word '>cfa': addr=188, immediate=False>,
    <Word '?': addr=1105, immediate=False>,
    <Word '@': addr=392, immediate=False>,
    <Word '[': addr=309, immediate=False>,
    <Word ']': addr=318, immediate=True>,
    <Word '^': addr=595, immediate=False>,
    <Word '_cstack': addr=599, immediate=False>,
    <Word '_dis': addr=261, immediate=False>,
    <Word 'b!': addr=423, immediate=False>,
    <Word 'b,': addr=231, immediate=False>,
    <Word 'b@': addr=402, immediate=False>,
    <Word 'branch': addr=440, immediate=True>,
    <Word 'bye': addr=482, immediate=False>,
    <Word 'create': addr=296, immediate=False>,
    <Word 'drop': addr=493, immediate=False>,
    <Word 'dup': addr=505, immediate=False>,
    <Word 'exit': addr=765, immediate=False>,
    <Word 'false': addr=579, immediate=False>,
    <Word 'find': addr=244, immediate=False>,
    <Word 'here': addr=573, immediate=False>,
    <Word 'immediate': addr=801, immediate=False>,
    <Word 'latest': addr=513, immediate=False>,
    <Word 'matmul': addr=555, immediate=False>,
    <Word 'mod': addr=633, immediate=False>,
    <Word 'nip': addr=488, immediate=False>,
    <Word 'none': addr=567, immediate=False>,
    <Word 'noop': addr=1121, immediate=False>,
    <Word 'nop': addr=501, immediate=False>,
    <Word 'over': addr=434, immediate=False>,
    <Word 'py::call': addr=851, immediate=False>,
    <Word 'py::getattr': addr=841, immediate=False>,
    <Word 'py::import': addr=831, immediate=False>,
    <Word 'rot': addr=497, immediate=False>,
    <Word 'swap': addr=611, immediate=False>,
    <Word 'true': addr=589, immediate=False>,
    <Word 'tuck': addr=1149, immediate=False>,
    <Word 'word': addr=172, immediate=False>,
    <Word 'words': addr=280, immediate=False>,
    <Word 'xor': addr=619, immediate=False>,
    <Word '|': addr=525, immediate=False>]

Base Context
------------

This is the disassembly of a base ``phorth`` context before any new words are
defined (including those in ``stdlib.fs``). This context uses 1000 bytes of
addressable memory, which does not leave much room for user defined words. This
is not even enough to hold the whole stdlib. Some key points are that the whole
context is wrapped in a ``try/except`` to catch any errors, report them, clear
the data and control stacks, and then jump back to the top of the repl. This
allows users to mistype words and not have the program crash. Also remember
that ``YIELD_VALUE`` instructions mean ``jmp``. There is a large segment of
``NOP`` instructions towards the bottom (I have stripped most of them) which is
the free memory space, or memory that is not used to define the
interpreter. This is where new words will be stored or can be used as mutable
memory by the program. The size of this space is configurable with the
``-m/--memory`` flag on the command line. It defaults to the max addressable
memory size of ``2 ** 16 - 1``

.. parsed-literal::

     1     >>    0 SETUP_EXCEPT           982 (to 985)
           >>    3 LOAD_CONST               0 (<built-in function push_return_addr>)
                 6 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
                 9 POP_TOP
                10 JUMP_ABSOLUTE          172
                13 DUP_TOP
                14 DUP_TOP
                15 LOAD_CONST               0 (<built-in function push_return_addr>)
                18 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
                21 POP_TOP
                22 JUMP_ABSOLUTE          244
                25 DUP_TOP
                26 LOAD_CONST               1 (None)
                29 COMPARE_OP               8 (is)
                32 POP_JUMP_IF_TRUE        87
                35 ROT_THREE
                36 POP_TOP
                37 POP_TOP
                38 DUP_TOP
                39 LOAD_ATTR                0 (addr)
                42 LOAD_CONST               2 (True)
                45 BINARY_SUBTRACT
                46 LOAD_FAST                0 (immediate)
                49 POP_JUMP_IF_TRUE        72
                52 ROT_TWO
                53 LOAD_ATTR                2 (immediate)
                56 POP_JUMP_IF_TRUE        74
                59 LOAD_CONST               0 (<built-in function push_return_addr>)
                62 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
                65 POP_TOP
                66 JUMP_ABSOLUTE          218
                69 JUMP_ABSOLUTE            3
           >>   72 ROT_TWO
                73 POP_TOP
           >>   74 LOAD_CONST               0 (<built-in function push_return_addr>)
                77 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
                80 POP_TOP
                81 YIELD_VALUE
                82 NOP
                83 NOP
                84 JUMP_ABSOLUTE            3
           >>   87 POP_TOP
                88 LOAD_CONST               3 (<function process_lit at 0x7f05c8228620>)
                91 ROT_TWO
                92 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
                95 DUP_TOP
                96 LOAD_CONST               4 (NotImplemented)
                99 COMPARE_OP               8 (is)
               102 POP_JUMP_IF_TRUE       145
               105 ROT_TWO
               106 POP_TOP
               107 LOAD_FAST                0 (immediate)
               110 POP_JUMP_IF_TRUE         3
               113 LOAD_CONST               5 (<built-in function append_lit>)
               116 ROT_TWO
               117 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               120 LOAD_CONST               6 (<built-in function comma_impl>)
               123 LOAD_CONST               7 (155)
               126 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               129 STORE_FAST               1 (here)
               132 LOAD_CONST               6 (<built-in function comma_impl>)
               135 ROT_TWO
               136 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               139 STORE_FAST               1 (here)
               142 JUMP_ABSOLUTE            3
           >>  145 POP_TOP
               146 LOAD_CONST               8 (<class 'phorth.code.UnknownWord'>)
               149 ROT_TWO
               150 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               153 RAISE_VARARGS            1
               156 LOAD_CONST               9 (<built-in function lit_impl>)
               159 LOAD_CONST              10 (<built-in function pop_return_addr>)
               162 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               165 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               168 UNPACK_SEQUENCE          2
               171 YIELD_VALUE
           >>  172 LOAD_CONST              11 (functools.partial(<built-in function next>, <generator object read_words at 0x7f05c8223db0>))
               175 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               178 JUMP_ABSOLUTE          181
           >>  181 LOAD_CONST              10 (<built-in function pop_return_addr>)
               184 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               187 YIELD_VALUE
           >>  188 DUP_TOP
               189 LOAD_CONST              12 (<class 'phorth.Word'>)
               192 LOAD_CONST              13 (<built-in function isinstance>)
               195 ROT_THREE
               196 CALL_FUNCTION            2 (2 positional, 0 keyword pair)
               199 POP_JUMP_IF_FALSE      208
               202 LOAD_ATTR                0 (addr)
               205 JUMP_ABSOLUTE          181
           >>  208 LOAD_CONST              14 (<class 'phorth.code.NotAWord'>)
               211 ROT_TWO
               212 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               215 RAISE_VARARGS            1
           >>  218 LOAD_CONST               6 (<built-in function comma_impl>)
               221 ROT_TWO
               222 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               225 STORE_FAST               1 (here)
               228 JUMP_ABSOLUTE          181
           >>  231 LOAD_CONST              15 (<built-in function bcomma_impl>)
               234 ROT_TWO
               235 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               238 STORE_FAST               1 (here)
               241 JUMP_ABSOLUTE          181
           >>  244 LOAD_CONST              16 (<built-in function find_impl>)
               247 ROT_TWO
               248 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               251 JUMP_ABSOLUTE          181
               254 LOAD_CONST              17 (<built-in function docol_impl>)
               257 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               260 YIELD_VALUE
               261 LOAD_CONST              18 (<function dis at 0x7f05ce428378>)
               264 LOAD_CONST              19 (<built-in function _getframe>)
               267 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               270 LOAD_ATTR                1 (f_code)
               273 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               276 POP_TOP
               277 JUMP_ABSOLUTE          181
               280 LOAD_CONST              20 (<toolz.functoolz.Compose object at 0x7f05c81cd978>)
               283 LOAD_CONST              21 (<built-in function globals>)
               286 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               289 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               292 POP_TOP
               293 JUMP_ABSOLUTE          181
           >>  296 LOAD_CONST              22 (<built-in function create_impl>)
               299 ROT_TWO
               300 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               303 STORE_FAST               2 (latest)
               306 JUMP_ABSOLUTE          181
           >>  309 LOAD_CONST              23 (False)
               312 STORE_FAST               0 (immediate)
               315 JUMP_ABSOLUTE          181
           >>  318 LOAD_CONST               2 (True)
               321 STORE_FAST               0 (immediate)
               324 JUMP_ABSOLUTE          181
               327 LOAD_CONST               0 (<built-in function push_return_addr>)
               330 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               333 POP_TOP
               334 JUMP_ABSOLUTE          172
               337 DUP_TOP
               338 LOAD_CONST               0 (<built-in function push_return_addr>)
               341 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               344 POP_TOP
               345 JUMP_ABSOLUTE          244
               348 DUP_TOP
               349 LOAD_CONST               1 (None)
               352 COMPARE_OP               8 (is)
               355 POP_JUMP_IF_TRUE       381
               358 ROT_TWO
               359 POP_TOP
               360 LOAD_CONST               0 (<built-in function push_return_addr>)
               363 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               366 POP_TOP
               367 JUMP_ABSOLUTE          188
               370 JUMP_ABSOLUTE          181
               373 POP_JUMP_IF_TRUE       381
               376 ROT_TWO
               377 POP_TOP
               378 JUMP_ABSOLUTE          181
           >>  381 POP_TOP
               382 LOAD_CONST               8 (<class 'phorth.code.UnknownWord'>)
               385 ROT_TWO
               386 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               389 RAISE_VARARGS            1
               392 LOAD_CONST              24 (<built-in function read_impl>)
               395 ROT_TWO
               396 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               399 JUMP_ABSOLUTE          181
               402 LOAD_CONST              25 (<built-in function bread_impl>)
               405 ROT_TWO
               406 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               409 JUMP_ABSOLUTE          181
               412 LOAD_CONST              26 (<built-in function write_impl>)
               415 ROT_THREE
               416 CALL_FUNCTION            2 (2 positional, 0 keyword pair)
               419 POP_TOP
               420 JUMP_ABSOLUTE          181
               423 LOAD_CONST              27 (<built-in function bwrite_impl>)
               426 ROT_THREE
               427 CALL_FUNCTION            2 (2 positional, 0 keyword pair)
               430 POP_TOP
               431 JUMP_ABSOLUTE          181
               434 ROT_TWO
               435 DUP_TOP
               436 ROT_THREE
               437 JUMP_ABSOLUTE          181
           >>  440 LOAD_CONST              28 (<built-in function branch_impl>)
               443 ROT_TWO
               444 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               447 YIELD_VALUE
               448 LOAD_CONST              23 (False)
               451 COMPARE_OP               2 (==)
               454 POP_JUMP_IF_TRUE       440
               457 YIELD_VALUE
               458 LOAD_CONST               1 (None)
               461 YIELD_VALUE
               462 LOAD_CONST              29 (<built-in function print_stack_impl>)
               465 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               468 POP_TOP
               469 JUMP_ABSOLUTE          181
               472 LOAD_CONST              30 (<built-in function divmod>)
               475 ROT_THREE
               476 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               479 JUMP_ABSOLUTE          181
               482 LOAD_CONST              31 (Done())
               485 RAISE_VARARGS            1
               488 ROT_TWO
               489 POP_TOP
               490 JUMP_ABSOLUTE          181
               493 LOAD_CONST               1 (None)
               496 JUMP_ABSOLUTE          181
               499 COMPARE_OP               2 (==)
               502 JUMP_ABSOLUTE          181
               505 COMPARE_OP               1 (<=)
               508 JUMP_ABSOLUTE          181
               511 BINARY_MULTIPLY
               512 JUMP_ABSOLUTE          181
               515 PRINT_EXPR
               516 JUMP_ABSOLUTE          181
               519 BINARY_ADD
               520 JUMP_ABSOLUTE          181
               523 BINARY_SUBTRACT
               524 JUMP_ABSOLUTE          181
               527 ROT_TWO
               528 JUMP_ABSOLUTE          181
               531 BINARY_LSHIFT
               532 JUMP_ABSOLUTE          181
               535 LOAD_FAST                3 (cstack)
               538 JUMP_ABSOLUTE          181
               541 BINARY_XOR
               542 JUMP_ABSOLUTE          181
               545 DUP_TOP
               546 JUMP_ABSOLUTE          181
               549 COMPARE_OP               0 (<)
               552 JUMP_ABSOLUTE          181
               555 BINARY_POWER
               556 JUMP_ABSOLUTE          181
               559 LOAD_CONST               2 (True)
               562 JUMP_ABSOLUTE          181
               565 BINARY_MODULO
               566 JUMP_ABSOLUTE          181
               569 BINARY_AND
               570 JUMP_ABSOLUTE          181
               573 LOAD_CONST              23 (False)
               576 JUMP_ABSOLUTE          181
               579 NOP
               580 JUMP_ABSOLUTE          181
               583 COMPARE_OP               5 (>=)
               586 JUMP_ABSOLUTE          181
               589 DUP_TOP_TWO
               590 JUMP_ABSOLUTE          181
               593 POP_TOP
               594 JUMP_ABSOLUTE          181
               597 COMPARE_OP               3 (!=)
               600 JUMP_ABSOLUTE          181
               603 LOAD_FAST                1 (here)
               606 JUMP_ABSOLUTE          181
               609 ROT_THREE
               610 JUMP_ABSOLUTE          181
               613 BINARY_RSHIFT
               614 JUMP_ABSOLUTE          181
               617 BINARY_OR
               618 JUMP_ABSOLUTE          181
               621 LOAD_FAST                2 (latest)
               624 JUMP_ABSOLUTE          181
               627 COMPARE_OP               4 (>)
               630 JUMP_ABSOLUTE          181
               633 BINARY_TRUE_DIVIDE
               634 JUMP_ABSOLUTE          181
               637 BINARY_MATRIX_MULTIPLY
               638 JUMP_ABSOLUTE          181
               641 LOAD_CONST               0 (<built-in function push_return_addr>)
               644 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               647 POP_TOP
               648 JUMP_ABSOLUTE          172
               651 LOAD_CONST               0 (<built-in function push_return_addr>)
               654 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               657 POP_TOP
               658 JUMP_ABSOLUTE          296
               661 LOAD_CONST              32 (100)
               664 LOAD_CONST               0 (<built-in function push_return_addr>)
               667 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               670 POP_TOP
               671 JUMP_ABSOLUTE          231
               674 LOAD_CONST              23 (False)
               677 LOAD_CONST               0 (<built-in function push_return_addr>)
               680 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               683 POP_TOP
               684 JUMP_ABSOLUTE          218
               687 LOAD_CONST              33 (131)
               690 LOAD_CONST               0 (<built-in function push_return_addr>)
               693 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               696 POP_TOP
               697 JUMP_ABSOLUTE          231
               700 LOAD_CONST              23 (False)
               703 LOAD_CONST               0 (<built-in function push_return_addr>)
               706 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               709 POP_TOP
               710 JUMP_ABSOLUTE          218
               713 LOAD_CONST               2 (True)
               716 LOAD_CONST               0 (<built-in function push_return_addr>)
               719 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               722 POP_TOP
               723 JUMP_ABSOLUTE          231
               726 LOAD_CONST              34 (113)
               729 LOAD_CONST               0 (<built-in function push_return_addr>)
               732 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               735 POP_TOP
               736 JUMP_ABSOLUTE          231
               739 LOAD_CONST              35 (254)
               742 LOAD_CONST               0 (<built-in function push_return_addr>)
               745 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               748 POP_TOP
               749 JUMP_ABSOLUTE          218
               752 LOAD_CONST               0 (<built-in function push_return_addr>)
               755 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               758 POP_TOP
               759 JUMP_ABSOLUTE          309
               762 JUMP_ABSOLUTE          181
               765 LOAD_CONST              36 (<function license_impl at 0x7f05c8228840>)
               768 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               771 POP_TOP
               772 JUMP_ABSOLUTE          181
               775 LOAD_CONST              10 (<built-in function pop_return_addr>)
               778 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               781 POP_TOP
               782 JUMP_ABSOLUTE          181
               785 LOAD_CONST              37 (774)
               788 LOAD_CONST               0 (<built-in function push_return_addr>)
               791 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               794 POP_TOP
               795 JUMP_ABSOLUTE          218
               798 LOAD_CONST               0 (<built-in function push_return_addr>)
               801 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               804 POP_TOP
               805 JUMP_ABSOLUTE          318
               808 JUMP_ABSOLUTE          181
               811 LOAD_CONST               2 (True)
               814 LOAD_FAST                2 (latest)
               817 STORE_ATTR               2 (immediate)
               820 JUMP_ABSOLUTE          181
           >>  823 LOAD_CONST              38 (')')
               826 LOAD_CONST              11 (functools.partial(<built-in function next>, <generator object read_words at 0x7f05c8223db0>))
               829 CALL_FUNCTION            0 (0 positional, 0 keyword pair)
               832 COMPARE_OP               2 (==)
               835 POP_JUMP_IF_FALSE      823
               838 JUMP_ABSOLUTE          181
               841 LOAD_CONST              39 (<built-in function __import__>)
               844 ROT_TWO
               845 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               848 JUMP_ABSOLUTE          181
               851 LOAD_CONST              40 (<built-in function getattr>)
               854 ROT_THREE
               855 CALL_FUNCTION            2 (2 positional, 0 keyword pair)
               858 JUMP_ABSOLUTE          181
               861 DUP_TOP
               862 LOAD_CONST              23 (False)
               865 COMPARE_OP               0 (<)
               868 POP_JUMP_IF_FALSE      886
               871 LOAD_CONST              41 ('nargs must be >= 0; got %s')
               874 ROT_TWO
               875 BINARY_MODULO
               876 LOAD_CONST              42 (<class 'ValueError'>)
               879 ROT_TWO
               880 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               883 RAISE_VARARGS            1
           >>  886 BUILD_LIST               0
               889 ROT_THREE
               890 ROT_THREE
               891 LIST_APPEND              1
               894 STORE_FAST               6 (tmp)
           >>  897 DUP_TOP
               898 LOAD_CONST              23 (False)
               901 COMPARE_OP               2 (==)
               904 POP_JUMP_IF_TRUE       924
               907 LOAD_CONST               2 (True)
               910 ROT_TWO
               911 BINARY_SUBTRACT
               912 LOAD_FAST                6 (tmp)
               915 ROT_THREE
               916 ROT_THREE
               917 LIST_APPEND              1
               920 POP_TOP
               921 JUMP_ABSOLUTE          897
           >>  924 POP_TOP
               925 LOAD_CONST              43 (<function py_call_impl at 0x7f05c82287b8>)
               928 LOAD_FAST                6 (tmp)
               931 CALL_FUNCTION_VAR        0 (0 positional, 0 keyword pair)
               934 JUMP_ABSOLUTE          181
               937 NOP
               938 NOP
               ...
               This is where the program's free memory goes. New words will go
               in this segment.
               ...
               983 NOP
               984 NOP
           >>  985 POP_TOP
               986 ROT_TWO
               987 POP_TOP
               988 LOAD_CONST              44 (<function handle_exception at 0x7f05c82282f0>)
               991 ROT_TWO
               992 CALL_FUNCTION            1 (1 positional, 0 keyword pair)
               995 POP_TOP
               996 POP_EXCEPT
               997 JUMP_ABSOLUTE            0


Dependencies
------------

``phorth`` is built with `codetransformer
<https://github.com/llllllllll/codetransformer>`_ which is a library for
manipulating CPython bytecode. It is normally used for defining trasformations
on bytecode produced by the CPython compiler; however, here it is used for the
richer definition of an instruction and the assembler.

The command line interface is built with `click
<https://github.com/pallets/click>`_. Click is by far my favorite cli parsing
library and I would encourage anyone building a cli to use it.

License
-------

``phorth`` is free software, available under the terms of the `GNU General
Public License, version 2 or later <http://gnu.org/licenses/gpl.html>`_. For
more information, see ``LICENSE``.
