/* -*- Mode: C; c-basic-offset: 4 -*- */
#ifdef HAVE_CONFIG_H
#  include "config.h"
#endif
#include <Python.h>
#include <pygtk.h>
#include <glade/glade.h>

void pylibglade_register_classes(PyObject *d);
extern PyMethodDef pylibglade_functions[];
extern PyExtensionClass PyGladeXML_Type;

DL_EXPORT(void)
initglade(void)
{
    PyObject *m, *d;

    m = Py_InitModule("gtk.glade", pylibglade_functions);
    d = PyModule_GetDict(m);

    init_pygobject();
    init_pygtk();

    glade_init();

    pylibglade_register_classes(d);

    if (PyErr_Occurred())
        Py_FatalError("could not initialise module gtk.libglade");
}
