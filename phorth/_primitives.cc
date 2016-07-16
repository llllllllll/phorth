#include <iostream>
#include <vector>

#include <Python.h>
#include <structmember.h>
#include <frameobject.h>
#include <libpy/libpy.h>
#include <libpy/automethod.h>

#include "phorth/constants.h"

using py::operator""_p;

struct wordobject {
    PyObject ob;
    py::object name;
    uint16_t addr;
    bool immediate;
};

static wordobject *innernewword(PyTypeObject *cls,
                                py::object name,
                                py::object addr,
                                py::object immediate) {
    wordobject *self = PyObject_New(wordobject, cls);

    if (!self) {
        return nullptr;
    }

    new(&self->name) py::object(name.incref());
    self->addr = py::long_::object(addr).as_unsigned_long();
    self->immediate = immediate.istrue();

    if (PyErr_Occurred()) {
        Py_DECREF(self);
        return nullptr;
    }

    return self;
}

static void deallocate(wordobject *self) {
    Py_CLEAR(self->name);
    PyObject_Del(self);
}

static wordobject *newword(PyTypeObject *cls,
                           PyObject *_args,
                           PyObject *kwargs) {
    if (kwargs && PyDict_Size(kwargs)) {
        PyErr_SetString(PyExc_TypeError,
                        "Word does not accept keywordobject arguments");
        return nullptr;
    }

    auto args = py::tuple::object(_args).as_nonnull();

    if (args.len() != 3) {
        PyErr_SetString(PyExc_TypeError,
                        "Word accepts exactly three positional arguments");
        return nullptr;
    }

    return innernewword(cls, args[0], args[1], args[2]);
}

static PyObject *wordrepr(wordobject *self) {
    return PyUnicode_FromFormat("<Word %R: addr=%d, immediate=%R>",
                                (PyObject*) self->name,
                                self->addr,
                                (PyObject*) (self->immediate ?
                                             py::True : py::False));
}

PyMemberDef members[] = {
    {"name", T_OBJECT_EX, offsetof(wordobject, name), READONLY, ""},
    {"addr", T_USHORT, offsetof(wordobject, addr), READONLY, ""},
    {"immediate", T_BOOL, offsetof(wordobject, immediate), 0, ""},
    {nullptr},
};

PyTypeObject wordtype = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "phorth.Word",                              // tp_name
    sizeof(wordobject),                         // tp_basicsize
    0,                                          // tp_itemsize
    (destructor) deallocate,                    // tp_dealloc
    0,                                          // tp_print
    0,                                          // tp_getattr
    0,                                          // tp_setattr
    0,                                          // tp_reserved
    (reprfunc) wordrepr,                        // tp_repr
    0,                                          // tp_as_number
    0,                                          // tp_as_sequence
    0,                                          // tp_as_mapping
    0,                                          // tp_hash
    0,                                          // tp_call
    0,                                          // tp_str
    0,                                          // tp_getattro
    0,                                          // tp_setattro
    0,                                          // tp_as_buffer
    Py_TPFLAGS_DEFAULT,                         // tp_flags
    0,                                          // tp_doc
    0,                                          // tp_traverse
    0,                                          // tp_clear
    0,                                          // tp_richcompare
    0,                                          // tp_weaklistoffset
    0,                                          // tp_iter
    0,                                          // tp_iternext
    0,                                          // tp_methods
    members,                                    // tp_members
    0,                                          // tp_getset
    0,                                          // tp_base
    0,                                          // tp_dict
    0,                                          // tp_descr_get
    0,                                          // tp_descr_set
    0,                                          // tp_dictoffset
    0,                                          // tp_init
    0,                                          // tp_alloc
    (newfunc) newword,                          // tp_new
};

class word : public py::object {
public:
    word() : py::object(nullptr) {}

    word(py::object name, py::object addr, py::object immediate=py::False)
        : py::object((PyObject*) innernewword(&wordtype,
                                              name,
                                              addr,
                                              immediate)) {}

    word(const py::object& pob) : py::object(pob) {
        if (!PyObject_IsInstance(pob, (PyObject*) &wordtype)) {
            PyErr_SetString(PyExc_TypeError,
                            "cannot create word from non Word object");
            ob = nullptr;
        }
    }

    word(const word &w) : py::object(w.ob) {}

    word(word &&mvfrom) : py::object((PyObject*) mvfrom) {
        mvfrom.ob = nullptr;
    }

    word &operator=(const word &w) {
        ob = w.ob;
        return *this;
    }

    word &operator=(word &&mvfrom) {
        ob = mvfrom.ob;
        mvfrom.ob = nullptr;
        return *this;
    }

    py::object name() const {
        return ((wordobject*) ob)->name;
    }

    uint16_t addr() const {
        return ((wordobject*) ob)->addr;
    }

    bool immediate() const {
        return ((wordobject*) ob)->immediate;
    }
};

namespace pyutils {
    template<>
    char typeformat<word> = 'O';  // automethod dispatch
}

py::type::object<word> Word((PyObject*) &wordtype);

static bool checkframe(PyFrameObject *f) {
    if (f->f_code->co_nlocals != EXPECTED_NLOCALS) {
        PyErr_Format(PyExc_AssertionError,
                     "frame has incorrect number nlocals, got %d, expected %d",
                     f->f_code->co_nlocals,
                     EXPECTED_NLOCALS);
        return false;
    }
    return true;
}

static PyFrameObject *getframe() {
    PyFrameObject *f;

    if (!(f = PyEval_GetFrame())) {
        PyErr_SetString(PyExc_AssertionError, "no frame running");
        return nullptr;
    }

    return checkframe(f) ? f : nullptr;
}

static inline char *frame_memory(PyFrameObject *f) {
    return PyBytes_AS_STRING(f->f_code->co_code);
}

/**
   Pop the return address off of the cstack.

   @return The address that was popped as a python integer.
*/
static py::object pop_return_addr(py::object) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    return std::move(py::object(f->f_localsplus[CSTACK]).getattr("pop"_p)());
}

/**
   Push the proper return value onto the cstack.

   @return None
*/
static py::object push_return_addr(py::object) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::list::object cstack(f->f_localsplus[CSTACK]);

    if (cstack.append(py::long_::object(f->f_lasti + 6).as_tmpref())) {
        return nullptr;
    }

    return py::None.incref();
}

/**
   Push the proper return value for a docol onto the cstack.

   @return None
*/
static py::object docol_impl(py::object) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::list::object cstack(f->f_localsplus[CSTACK]);
    return std::move(-(cstack.getattr("pop"_p)() + 1_p));
}

/**
   Implmentation for the branch forth word.

   @param unused
   @param distance The amount to add to the current top of the cstack.
   @return The location to jump to.
*/
static py::object branch_impl(py::object self, py::object distance) {
    // subtract 1 because we yield the value of last_i which is 1 less than
    // the index we want to jump to
    return std::move(pop_return_addr(self) + distance - 1_p);
}

/**
   Implementation for the @ forth word.

   ( addr -- n )

   @param unused
   @param addr The address into the co_code to read.
   @return The value at that address.
*/
static py::object read_impl(py::object, uint16_t addr) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    return py::long_::object(*((uint16_t*) &frame_memory(f)[addr]));
}

/**
   Implementation for the b@ forth word.

   ( addr -- n )

   @param unused
   @param addr The address into the co_code to read.
   @return The value at that address.
*/
static py::object bread_impl(py::object, uint16_t addr) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    return py::long_::object(*((uint8_t*) &frame_memory(f)[addr]));
}

/**
   Implementation for the ! forth word.

   ( addr n -- )

   @param unused
   @param addr The address into the co_code to write to.
   @param value The value to write into `addr`.
   @return None.
*/
static py::object write_impl(py::object,
                             uint16_t addr,
                             uint16_t val) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    *((uint16_t*) &frame_memory(f)[addr]) = val;
    return py::None.incref();
}

/**
   Implementation for the b! forth word.

   ( addr n -- )

   @param unused
   @param addr The address into the co_code to write to.
   @param value The value to write into `addr`.
   @return None.
*/
static py::object bwrite_impl(py::object,
                              uint16_t addr,
                              uint8_t val) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    *((uint8_t*) &frame_memory(f)[addr]) = val;
    return py::None.incref();
}

/**
   Implementation for the find forth word.

   ( str -- word )

   @param unused
   @param str The name to lookup
   @return The word with that name or None
*/
static py::object find_impl(py::object, py::object word) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::object ret = PyDict_GetItem(f->f_globals, word);

    if (!ret.is_nonnull()) {
        ret = py::None;
    }

    return ret.incref();
}

static py::object print_stack_impl(py::object) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    std::size_t stack_size = ((py::long_::object)
                             f->f_localsplus[STACK_SIZE]).as_size_t();
    std::cout << '<' << stack_size << '>';

    for (std::size_t n = 0; n < stack_size; ++n) {
        std::cout << ' ' << ((py::object) f->f_valuestack[n]).repr();
    }
    std::cout << std::endl;
    return py::None.incref();
}

static py::object clear_cstack(py::object, PyObject *fo) {
    if (!PyObject_IsInstance(fo, (PyObject*) &PyFrame_Type)) {
        PyErr_SetString(PyExc_TypeError,
                        "f must be a frame object");
        return nullptr;
    }

    PyFrameObject *f = (PyFrameObject*) (PyObject*) fo;
    if (!checkframe(f)) {
        return nullptr;
    }

    py::object cstack(f->f_localsplus[CSTACK]);

    if (!(f->f_localsplus[CSTACK] = PyList_New(0))) {
        f->f_localsplus[CSTACK] = cstack;
        return nullptr;
    }

    return cstack.incref();
}

static py::object create_impl(py::object, py::object name) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    word latest(Word(name,
                     py::object(f->f_localsplus[HERE]),
                     py::False));
    if (!latest.is_nonnull()) {
        return nullptr;
    }

    if (py::object(f->f_globals).setitem(name, latest)) {
        latest.decref();
        return nullptr;
    }
    return latest;
}

static py::object comma_impl(py::object, uint16_t val) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::long_::object here(f->f_localsplus[HERE]);
    *((uint16_t*) &frame_memory(f)[here.as_size_t()]) = val;
    return std::move(here + 2_p);
}

static py::object bcomma_impl(py::object, uint8_t val) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::long_::object here(f->f_localsplus[HERE]);
    *((uint8_t*) &frame_memory(f)[here.as_size_t()]) = val;
    return std::move(here + 1_p);
}

static py::object append_lit(py::object, py::object lit) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::list::object literals(f->f_localsplus[LITERALS]);
    literals.append(lit);
    return py::long_::object(literals.len() - 1);
}

static py::object lit_impl(py::object, py::object ret) {
    PyFrameObject *f;

    if (!(f = getframe())) {
        return nullptr;
    }

    py::list::object literals(f->f_localsplus[LITERALS]);
    auto idx = -py::long_::object(ret).as_long();

    if (PyErr_Occurred()) {
        return nullptr;
    }

    auto lit = literals[(std::size_t) *((uint16_t*) &frame_memory(f)[idx])];
    return py::tuple::pack(ret - 2_p, lit);
}

static PyMethodDef methods[] = {
    automethod(pop_return_addr),
    automethod(push_return_addr),
    automethod(docol_impl),
    automethod(branch_impl),
    automethod(read_impl),
    automethod(bread_impl),
    automethod(write_impl),
    automethod(bwrite_impl),
    automethod(find_impl),
    automethod(print_stack_impl),
    automethod(clear_cstack),
    automethod(comma_impl),
    automethod(create_impl),
    automethod(bcomma_impl),
    automethod(append_lit),
    automethod(lit_impl),
    {nullptr},
};

PyDoc_STRVAR(module_doc,
             "Primitive phorth operations.\n"
             "It is unsafe to call these functions outside of the context of\n"
             "a phorth stackframe.\n");

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "phorth._primitives",
    module_doc,
    -1,
    methods,
};

PyMODINIT_FUNC
PyInit__primitives(void)
{
    if (PyType_Ready(&wordtype)) {
        return nullptr;
    }

    py::object m(PyModule_Create(&module));
    if (m.setattr("argnames"_p, py::tuple::pack("immediate"_p,
                                                "here"_p,
                                                "latest"_p,
                                                "cstack"_p,
                                                "stack_size"_p,
                                                "literals"_p,
                                                "tmp"_p))) {
        return nullptr;
    }
    if (m.setattr("Word"_p, Word)) {
        return nullptr;
    }

    return m;
}
