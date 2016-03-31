#include <cstdint>

#include <Python.h>
#include <frameobject.h>
#include <libpy/automethod.h>
#include <libpy/libpy.h>

#include "phorth/constants.h"

using py::operator""_p;

static py::tmpref<py::object> jump(PyGenObject *gen, py::object arg)
    {
        PyThreadState *tstate = PyThreadState_GET();
        PyFrameObject *f = gen->gi_frame;

        if (gen->gi_running) {
            PyErr_SetString(PyExc_ValueError,
                            "generator already executing");
            return nullptr;
        }
        if (!(f && f->f_stacktop)) {
            return nullptr;
        }

        if (f->f_lasti == -1) {
            if (arg.is_nonnull() && !arg.is(py::None)) {
                PyErr_SetString(PyExc_AssertionError,
                                "tried to prime with non None value");
                return nullptr;
            }
        } else if (!arg.is(py::None)) {
            // when arg is None we should just send right back in to the same
            // place
            // set the f_lasti to the jump index
            py::long_::object jump_index = arg;

            if (!jump_index.is_nonnull()) {
                return nullptr;
            }

            long idx = jump_index.as_long();

            if (idx < 0) {
                // idx < 0 means we do a deref jump, this is used to implement
                // the DTC model. Note that we are using the absolute value
                // as the address, the sign is just used to say what kind of
                // jump to use.
                py::list::object cstack(f->f_localsplus[CSTACK]);
                cstack.append(py::long_::object(idx - 2).as_tmpref());
                idx = *((uint16_t*)
                        &PyBytes_AS_STRING(f->f_code->co_code)[-idx]);
            }

            f->f_lasti = idx;
        }

        /* Generators always return to their most recent caller, not
         * necessarily their creator. */
        Py_XINCREF(tstate->frame);
        assert(f->f_back == nullptr);
        f->f_back = tstate->frame;

        gen->gi_running = 1;
        py::tmpref<py::object> result (PyEval_EvalFrameEx(f, 0));
        gen->gi_running = 0;

        /* Don't keep the reference to f_back any longer than necessary.  It
         * may keep a chain of frames alive or it could create a reference
         * cycle. */
        assert(f->f_back == tstate->frame);
        Py_CLEAR(f->f_back);

        /* If the generator just returned (as opposed to yielding), raise an
           assertion error. */
        if (result.is_nonnull() && f->f_stacktop == nullptr) {
            PyErr_SetString(PyExc_AssertionError, "generator stopped");
            result.clear();
        }

        if (!result.is_nonnull() || f->f_stacktop == nullptr) {
            /* generator can't be rerun, so release the frame */
            /* first clean reference cycle through stored exception traceback */
            PyObject *t, *v, *tb;
            t = f->f_exc_type;
            v = f->f_exc_value;
            tb = f->f_exc_traceback;
            f->f_exc_type = nullptr;
            f->f_exc_value = nullptr;
            f->f_exc_traceback = nullptr;
            Py_XDECREF(t);
            Py_XDECREF(v);
            Py_XDECREF(tb);
            gen->gi_frame->f_gen = nullptr;
            gen->gi_frame = nullptr;
            Py_DECREF(f);

            if (result.is_nonnull()) {
                result.clear();
            }
        }
        else {
            // set the stack size for use later
            f->f_localsplus[STACK_SIZE] = py::long_::object(f->f_stacktop -
                                                            f->f_valuestack);
        }

        return result;
    }

static inline py::tmpref<py::object> prime(PyGenObject *gen) {
    return jump(gen, py::None);
}

static py::object
jump_handler(py::object, py::object gen) {
    if (!PyGen_CheckExact(gen)) {
        PyErr_SetString(PyExc_AssertionError,
                        "gen must be a generator");
    }

    py::object jump_index = prime((PyGenObject*) (PyObject*) gen);

    while (jump_index.is_nonnull()) {
        py::tmpref<py::object> cleanup((PyObject*) jump_index);
         jump_index = jump((PyGenObject*) (PyObject*) gen, jump_index);
     }
    return nullptr;
}

static PyMethodDef methods[] = {
    automethod(jump_handler),
    {nullptr},
};

PyDoc_STRVAR(module_doc,
             "Execution of a phorth context.\n");

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "phorth._runner",
    module_doc,
    -1,
    methods,
};

PyMODINIT_FUNC
PyInit__runner(void)
{
    return PyModule_Create(&module);
}
