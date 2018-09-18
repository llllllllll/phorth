#include <array>
#include <cstdio>
#include <optional>
#include <tuple>
#include <vector>

#include <Python.h>
#include <frameobject.h>
#include <structmember.h>

#include "phorth/constants.h"

namespace phorth {
struct word {
    PyObject ob;
    PyObject* name;
    std::uint16_t addr;
    bool immediate;
};

namespace detail {
template<typename T, bool = std::is_unsigned_v<T>>
struct large_int {
    using type = std::size_t;
};

template<typename T>
struct large_int<T, false> {
    using type = Py_ssize_t;
};
}  // namespace detail

template<typename T>
std::optional<T> ob_as_int(PyObject* ob) {
    typename detail::large_int<T>::type addr_int;
    if (std::is_unsigned_v<T>) {
        addr_int = PyLong_AsSize_t(ob);
    }
    else {
        addr_int = PyLong_AsSsize_t(ob);
    }

    if (PyErr_Occurred() || addr_int > std::numeric_limits<T>::max()) {
        PyErr_Format(PyExc_OverflowError, "value would overflow: %R", ob);
        return {};
    }

    return {static_cast<T>(addr_int)};
}

word* innernewword(PyTypeObject* cls, PyObject* name, PyObject* addr_ob, bool immediate) {
    word* self = PyObject_New(word, cls);

    if (!self) {
        return nullptr;
    }

    auto addr = ob_as_int<std::uint16_t>(addr_ob);
    if (!addr) {
        return nullptr;
    }

    Py_INCREF(name);
    self->name = name;
    self->addr = *addr;
    self->immediate = immediate;
    return self;
}

void deallocate(word* self) {
    Py_CLEAR(self->name);
    PyObject_Del(self);
}

word* newword(PyTypeObject* cls, PyObject* args, PyObject* kwargs) {
    const char* const keywords[] = {"name", "addr", "immediate", nullptr};

    PyObject* name;
    PyObject* addr;
    int immediate;
    if (!PyArg_ParseTupleAndKeywords(args,
                                     kwargs,
                                     "OOp",
                                     const_cast<char**>(keywords),
                                     &name,
                                     &addr,
                                     &immediate)) {
        return nullptr;
    }

    return innernewword(cls, name, addr, immediate);
}

PyObject* wordrepr(word* self) {
    return PyUnicode_FromFormat("<Word %R: addr=%d, immediate=%s>",
                                self->name,
                                self->addr,
                                (self->immediate ? "True" : "False"));
}

PyMemberDef members[] = {
    {"name", T_OBJECT_EX, offsetof(word, name), READONLY, ""},
    {"addr", T_USHORT, offsetof(word, addr), READONLY, ""},
    {"immediate", T_BOOL, offsetof(word, immediate), 0, ""},
    {nullptr},
};

PyTypeObject wordtype = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0) "phorth.Word",  // tp_name
    sizeof(word),                                          // tp_basicsize
    0,                                                     // tp_itemsize
    (destructor) deallocate,                               // tp_dealloc
    0,                                                     // tp_print
    0,                                                     // tp_getattr
    0,                                                     // tp_setattr
    0,                                                     // tp_reserved
    (reprfunc) wordrepr,                                   // tp_repr
    0,                                                     // tp_as_number
    0,                                                     // tp_as_sequence
    0,                                                     // tp_as_mapping
    0,                                                     // tp_hash
    0,                                                     // tp_call
    0,                                                     // tp_str
    0,                                                     // tp_getattro
    0,                                                     // tp_setattro
    0,                                                     // tp_as_buffer
    Py_TPFLAGS_DEFAULT,                                    // tp_flags
    0,                                                     // tp_doc
    0,                                                     // tp_traverse
    0,                                                     // tp_clear
    0,                                                     // tp_richcompare
    0,                                                     // tp_weaklistoffset
    0,                                                     // tp_iter
    0,                                                     // tp_iternext
    0,                                                     // tp_methods
    members,                                               // tp_members
    0,                                                     // tp_getset
    0,                                                     // tp_base
    0,                                                     // tp_dict
    0,                                                     // tp_descr_get
    0,                                                     // tp_descr_set
    0,                                                     // tp_dictoffset
    0,                                                     // tp_init
    0,                                                     // tp_alloc
    (newfunc) newword,                                     // tp_new
};

bool checkframe(PyFrameObject* f) {
    if (f->f_code->co_nlocals != EXPECTED_NLOCALS) {
        PyErr_Format(PyExc_AssertionError,
                     "frame has incorrect number nlocals, got %d, expected %d",
                     f->f_code->co_nlocals,
                     EXPECTED_NLOCALS);
        return false;
    }
    return true;
}

PyFrameObject* getframe() {
    PyFrameObject* f;

    if (!(f = PyEval_GetFrame())) {
        PyErr_SetString(PyExc_AssertionError, "no frame running");
        return nullptr;
    }

    return checkframe(f) ? f : nullptr;
}

inline char* frame_memory(PyFrameObject* f) {
    return PyBytes_AS_STRING(f->f_code->co_code);
}

template<typename Char, Char... cs>
std::integer_sequence<Char, cs...> operator""_add_method_literal() {
    return {};
}

namespace detail {
std::vector<PyMethodDef> methods;

template<typename T, int flags>
struct add_method;

template<char... cs, int flags>
struct add_method<std::integer_sequence<char, cs...>, flags> {
private:
    static constexpr std::array<char, sizeof...(cs) + 1> name = {cs..., '\0'};

public:
    add_method(PyCFunction meth) {
        PyMethodDef m = {name.data(), meth, flags, nullptr};
        methods.emplace_back(m);
    }
};
}  // namespace detail

#define CAT_IMPL(a, b) a##b
#define CAT(a, b) CAT_IMPL(a, b)
#define METHOD(name, flags, ...)                                                         \
    PyObject* name(__VA_ARGS__);                                                         \
    detail::add_method<decltype(#name##_add_method_literal), flags> CAT(_add_method_,    \
                                                                        __COUNTER__)(    \
        reinterpret_cast<PyCFunction>(name));                                            \
    PyObject* name(__VA_ARGS__)

/**
   Pop the return address off of the cstack.

   @return The address that was popped as a python integer.
*/
METHOD(pop_return_addr, METH_NOARGS, PyObject*) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* cstack = f->f_localsplus[CSTACK];
    return PyObject_CallMethod(cstack, "pop", nullptr);
}

/**
   Push the proper return value onto the cstack.

   @return None
*/
METHOD(push_return_addr, METH_NOARGS, PyObject*) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* return_addr = PyLong_FromLong(f->f_lasti + 6);
    if (!return_addr) {
        return nullptr;
    }

    PyObject* cstack = f->f_localsplus[CSTACK];
    int err = PyList_Append(cstack, return_addr);
    Py_DECREF(return_addr);
    if (err) {
        return nullptr;
    }

    Py_RETURN_NONE;
}

/**
   Push the proper return value for a docol onto the cstack.

   @return None
*/
METHOD(docol_impl, METH_NOARGS, PyObject*) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* cstack = f->f_localsplus[CSTACK];
    PyObject* addr_ob = PyObject_CallMethod(cstack, "pop", nullptr);
    if (!addr_ob) {
        return nullptr;
    }
    long addr = PyLong_AsLong(addr_ob);
    if (PyErr_Occurred()) {
        return nullptr;
    }
    Py_DECREF(addr_ob);

    return PyLong_FromLong(-(addr + 1));
}

/**
   Implmentation for the branch forth word.

   @param unused
   @param distance The amount to add to the current top of the cstack.
   @return The location to jump to.
*/
METHOD(branch_impl, METH_O, PyObject* self, PyObject* distance_ob) {
    PyObject* base_ob = pop_return_addr(self);
    if (!base_ob) {
        return nullptr;
    }
    auto base = ob_as_int<std::uint16_t>(base_ob);
    Py_DECREF(base_ob);
    if (!base) {
        return nullptr;
    }

    auto distance = ob_as_int<std::int16_t>(distance_ob);
    if (!distance) {
        return nullptr;
    }

    // subtract 1 because we yield the value of last_i which is 1 less than
    // the index we want to jump to
    return PyLong_FromUnsignedLong(*base + *distance - 1);
}

/**
   Implementation for the @ forth word.

   ( addr -- n )

   @param unused
   @param addr The address into the co_code to read.
   @return The value at that address.
*/
METHOD(read_impl, METH_O, PyObject*, PyObject* addr_ob) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    auto addr = ob_as_int<std::uint16_t>(addr_ob);
    if (!addr) {
        return nullptr;
    }
    return PyLong_FromLong(*reinterpret_cast<std::uint16_t*>(&frame_memory(f)[*addr]));
}

/**
   Implementation for the b@ forth word.

   ( addr -- n )

   @param unused
   @param addr The address into the co_code to read.
   @return The value at that address.
*/
METHOD(bread_impl, METH_O, PyObject*, PyObject* addr_ob) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    auto addr = ob_as_int<std::uint16_t>(addr_ob);
    if (!addr) {
        return nullptr;
    }
    return PyLong_FromLong(*reinterpret_cast<std::uint8_t*>(&frame_memory(f)[*addr]));
}

/**
   Implementation for the ! forth word.

   ( addr n -- )

   @param unused
   @param addr The address into the co_code to write to.
   @param value The value to write into `addr`.
   @return None.
*/
METHOD(write_impl, METH_VARARGS, PyObject*, PyObject* args) {
    if (PyTuple_GET_SIZE(args) != 2) {
        PyErr_SetString(PyExc_TypeError, "write_impl expects exactly 2 args");
        return nullptr;
    }

    PyFrameObject* f;
    if (!(f = getframe())) {
        return nullptr;
    }

    auto addr = ob_as_int<std::uint16_t>(PyTuple_GET_ITEM(args, 0));
    if (!addr) {
        return nullptr;
    }
    auto val = ob_as_int<std::uint16_t>(PyTuple_GET_ITEM(args, 1));
    if (!val) {
        return nullptr;
    }

    *reinterpret_cast<std::uint16_t*>(&frame_memory(f)[*addr]) = *val;
    Py_RETURN_NONE;
}

/**
   Implementation for the b! forth word.

   ( addr n -- )

   @param unused
   @param addr The address into the co_code to write to.
   @param value The value to write into `addr`.
   @return None.
*/
METHOD(bwrite_impl, METH_VARARGS, PyObject*, PyObject* args) {
    if (PyTuple_GET_SIZE(args) != 2) {
        PyErr_SetString(PyExc_TypeError, "write_impl expects exactly 2 args");
        return nullptr;
    }

    PyFrameObject* f;
    if (!(f = getframe())) {
        return nullptr;
    }

    auto addr = ob_as_int<std::uint16_t>(PyTuple_GET_ITEM(args, 0));
    if (!addr) {
        return nullptr;
    }
    auto val = ob_as_int<std::uint8_t>(PyTuple_GET_ITEM(args, 1));
    if (!val) {
        return nullptr;
    }

    *reinterpret_cast<std::uint8_t*>(&frame_memory(f)[*addr]) = *val;
    Py_RETURN_NONE;
}

/**
   Implementation for the find forth word.

   ( str -- word )

   @param unused
   @param word The name to lookup
   @return The word with that name or None
*/
METHOD(find_impl, METH_O, PyObject*, PyObject* word) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* ret = PyDict_GetItem(f->f_globals, word);
    if (!ret) {
        ret = Py_None;
    }

    Py_INCREF(ret);
    return ret;
}

METHOD(print_stack_impl, METH_NOARGS, PyObject*) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* stack_size_ob = f->f_localsplus[STACK_SIZE];
    auto stack_size = ob_as_int<std::size_t>(stack_size_ob);
    if (!stack_size) {
        return nullptr;
    }
    std::fprintf(stdout, "<%ld>", *stack_size);

    for (std::size_t n = 0; n < *stack_size; ++n) {
        std::fputc(' ', stdout);
        PyObject_Print(f->f_valuestack[n], stdout, 0);
    }
    std::fputc('\n', stdout);
    Py_RETURN_NONE;
}

METHOD(clear_cstack, METH_O, PyObject*, PyObject* fo) {
    if (!PyObject_IsInstance(fo, reinterpret_cast<PyObject*>(&PyFrame_Type))) {
        PyErr_SetString(PyExc_TypeError, "f must be a frame object");
        return nullptr;
    }

    auto f = reinterpret_cast<PyFrameObject*>(fo);
    if (!checkframe(f)) {
        return nullptr;
    }

    PyObject* cstack = f->f_localsplus[CSTACK];

    if (!(f->f_localsplus[CSTACK] = PyList_New(0))) {
        f->f_localsplus[CSTACK] = cstack;
        return nullptr;
    }

    return cstack;
}

METHOD(create_impl, METH_O, PyObject*, PyObject* name) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    word* latest = innernewword(&wordtype, name, f->f_localsplus[HERE], false);
    if (!latest) {
        return nullptr;
    }

    if (PyDict_SetItem(f->f_globals, name, reinterpret_cast<PyObject*>(latest))) {
        Py_DECREF(latest);
        return nullptr;
    }

    return reinterpret_cast<PyObject*>(latest);
}

METHOD(comma_impl, METH_O, PyObject*, PyObject* val_ob) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    auto val = ob_as_int<std::uint16_t>(val_ob);
    if (!val) {
        return nullptr;
    }
    auto here = ob_as_int<std::uint16_t>(f->f_localsplus[HERE]);
    if (!here) {
        return nullptr;
    }
    *reinterpret_cast<std::uint16_t*>(&frame_memory(f)[*here]) = *val;

    return PyLong_FromUnsignedLong(*here + 2);
}

METHOD(bcomma_impl, METH_O, PyObject*, PyObject* val_ob) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    auto val = ob_as_int<std::uint8_t>(val_ob);
    if (!val) {
        return nullptr;
    }
    auto here = ob_as_int<std::uint16_t>(f->f_localsplus[HERE]);
    if (!here) {
        return nullptr;
    }
    *reinterpret_cast<std::uint8_t*>(&frame_memory(f)[*here]) = *val;

    return PyLong_FromUnsignedLong(*here + 1);
}

METHOD(append_lit, METH_O, PyObject*, PyObject* lit) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    PyObject* literals = f->f_localsplus[LITERALS];
    if (PyList_Append(literals, lit)) {
        return nullptr;
    }

    return PyLong_FromSsize_t(PyList_GET_SIZE(literals) - 1);
}

METHOD(lit_impl, METH_O, PyObject*, PyObject* ret_ob) {
    PyFrameObject* f;

    if (!(f = getframe())) {
        return nullptr;
    }

    auto ret = ob_as_int<long>(ret_ob);
    if (!ret) {
        return nullptr;
    }
    PyObject* literals = f->f_localsplus[LITERALS];
    long idx = -*ret;

    PyObject* lit = PyList_GET_ITEM(literals,
                                    *reinterpret_cast<std::uint16_t*>(
                                        &frame_memory(f)[idx]));

    PyObject* new_ret = PyLong_FromLong(*ret - 2);
    if (!new_ret) {
        return nullptr;
    }

    PyObject* out = PyTuple_Pack(2, new_ret, lit);
    Py_DECREF(new_ret);
    return out;
}

PyDoc_STRVAR(module_doc,
             "Primitive phorth operations.\n"
             "It is unsafe to call these functions outside of the context of\n"
             "a phorth stackframe.\n");

PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "phorth._primitives",
    module_doc,
    -1,
    nullptr,
};

PyMODINIT_FUNC PyInit__primitives(void) {
    if (PyType_Ready(&wordtype)) {
        return nullptr;
    }

    PyMethodDef end = {nullptr};
    detail::methods.emplace_back(end);
    module.m_methods = detail::methods.data();
    PyObject* m = PyModule_Create(&module);
    if (!m) {
        return nullptr;
    }

    std::array<char, EXPECTED_NLOCALS + 3> fmt;
    memset(fmt.data(), 's', fmt.size());
    fmt[0] = '(';
    fmt[fmt.size() - 2] = ')';
    fmt[fmt.size() - 1] = '\0';

    std::array<char*, EXPECTED_NLOCALS + 1> build_value_args = {fmt.data()};

    auto locals = &build_value_args[1];
    locals[IMMEDIATE_MODE] = "immediate";
    locals[HERE] = "here";
    locals[LATEST] = "latest";
    locals[CSTACK] = "cstack";
    locals[STACK_SIZE] = "stack_size";
    locals[LITERALS] = "literals";
    locals[TMP] = "tmp";

    for (std::size_t ix = 0; ix < EXPECTED_NLOCALS; ++ix) {
        if (!locals[ix]) {
            PyErr_Format(PyExc_AssertionError, "argnames[%ld] == nullptr");
            Py_DECREF(m);
            return nullptr;
        }
    }

    PyObject* argnames = std::apply(Py_BuildValue, build_value_args);
    if (!argnames) {
        Py_DECREF(m);
        return nullptr;
    }

    int err = PyObject_SetAttrString(m, "argnames", argnames);
    Py_DECREF(argnames);
    if (err) {
        Py_DECREF(m);
        return nullptr;
    }

    if (PyObject_SetAttrString(m, "Word", reinterpret_cast<PyObject*>(&wordtype))) {
        Py_DECREF(m);
        return nullptr;
    }

    return m;
}
}  // namespace phorth
