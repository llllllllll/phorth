#include <cstdint>

#include <Python.h>
#include <frameobject.h>

#include "phorth/constants.h"

namespace phorth {
PyObject* jump(PyGenObject* gen, PyObject* arg) {
    PyThreadState* tstate = PyThreadState_GET();
    PyFrameObject* f = gen->gi_frame;

    if (gen->gi_running) {
        PyErr_SetString(PyExc_ValueError, "generator already executing");
        return nullptr;
    }
    if (!(f && f->f_stacktop)) {
        return nullptr;
    }

    if (f->f_lasti == -1) {
        if (arg != Py_None) {
            PyErr_SetString(PyExc_AssertionError, "tried to prime with non None value");
            return nullptr;
        }
    }
    else if (arg != Py_None) {
        // when arg is None we should just send right back in to the same
        // place set the f_lasti to the jump index
        long idx = PyLong_AsLong(arg);
        if (PyErr_Occurred()) {
            return nullptr;
        }

        if (idx < 0) {
            // idx < 0 means we do a deref jump, this is used to implement
            // the DTC model. Note that we are using the absolute value
            // as the address, the sign is just used to say what kind of
            // jump to use.
            PyObject* cstack = f->f_localsplus[CSTACK];
            PyObject* new_ix = PyLong_FromLong(idx - 2);
            if (!new_ix) {
                return nullptr;
            }
            int err = PyList_Append(cstack, new_ix);
            Py_DECREF(new_ix);
            if (err) {
                return nullptr;
            }
            idx = *reinterpret_cast<std::uint16_t*>(
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
    PyObject* result = PyEval_EvalFrameEx(f, 0);
    gen->gi_running = 0;

    /* Don't keep the reference to f_back any longer than necessary.  It
     * may keep a chain of frames alive or it could create a reference
     * cycle. */
    assert(f->f_back == tstate->frame);
    Py_CLEAR(f->f_back);

    /* If the generator just returned (as opposed to yielding), raise an
       assertion error. */
    if (result && f->f_stacktop == nullptr) {
        PyErr_SetString(PyExc_AssertionError, "generator stopped");
        Py_CLEAR(result);
    }

    if (!result || f->f_stacktop == nullptr) {
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

        if (result) {
            Py_CLEAR(result);
        }
    }
    else {
        // set the stack size for use later
        PyObject* stack_size = PyLong_FromLong(f->f_stacktop - f->f_valuestack);
        if (!stack_size) {
            Py_CLEAR(result);
            return nullptr;
        }
        Py_DECREF(f->f_localsplus[STACK_SIZE]);
        f->f_localsplus[STACK_SIZE] = stack_size;
    }

    return result;
}

PyObject* prime(PyGenObject* gen) {
    return jump(gen, Py_None);
}

PyObject* jump_handler(PyObject*, PyObject* gen) {
    if (!PyGen_CheckExact(gen)) {
        PyErr_SetString(PyExc_AssertionError, "gen must be a generator");
        return nullptr;
    }

    PyObject* jump_index = prime(reinterpret_cast<PyGenObject*>(gen));
    while (jump_index) {
        PyObject* tmp = jump(reinterpret_cast<PyGenObject*>(gen), jump_index);
        Py_DECREF(jump_index);
        jump_index = tmp;
    }

    return nullptr;
}

static PyMethodDef methods[] = {
    {"jump_handler", reinterpret_cast<PyCFunction>(jump_handler), METH_O, nullptr},
    {nullptr},
};

PyDoc_STRVAR(module_doc, "Execution of a phorth context.\n");

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "phorth._runner",
    module_doc,
    -1,
    methods,
};

PyMODINIT_FUNC PyInit__runner(void) {
    return PyModule_Create(&module);
}
}  // namespace phorth
