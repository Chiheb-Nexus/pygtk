import sys, os, string
import getopt, traceback, keyword
import defsparser, argtypes, override

def exc_info():
    #traceback.print_exc()
    etype, value, tb = sys.exc_info()
    ret = ""
    try:
        sval = str(value)
        if etype == KeyError:
            ret = "No ArgType for %s" % (sval,)
        else:
            ret = sval
    finally:
        del etype, value, tb
    return ret

def fixname(name):
    if keyword.iskeyword(name):
	return name + '_'
    return name

class FileOutput:
    '''Simple wrapper for file object, that makes writing #line
    statements easier.''' # "
    def __init__(self, fp, filename=None):
        self.fp = fp
        self.lineno = 1
        if filename:
            self.filename = filename
        else:
            self.filename = self.fp.name
    # handle writing to the file, and keep track of the line number ...
    def write(self, str):
        self.fp.write(str)
        self.lineno = self.lineno + string.count(str, '\n')
    def writelines(self, sequence):
        for line in sequence:
            self.write(line)
    def close(self):
        self.fp.close()
    def flush(self):
        self.fp.flush()

    def setline(self, linenum, filename):
        '''writes out a #line statement, for use by the C
        preprocessor.''' # "
        self.write('#line %d "%s"\n' % (linenum, filename))
    def resetline(self):
        '''resets line numbering to the original file'''
        self.setline(self.lineno + 1, self.filename)

class Wrapper:
    type_tmpl = \
        'PyTypeObject Py%(typename)s_Type = {\n' \
        '    PyObject_HEAD_INIT(NULL)\n' \
        '    0,					/* ob_size */\n' \
        '    "%(classname)s",			/* tp_name */\n' \
        '    sizeof(%(tp_basicsize)s),	        /* tp_basicsize */\n' \
        '    0,					/* tp_itemsize */\n' \
        '    /* methods */\n' \
        '    (destructor)0,			/* tp_dealloc */\n' \
        '    (printfunc)0,			/* tp_print */\n' \
        '    (getattrfunc)%(tp_getattr)s,	/* tp_getattr */\n' \
        '    (setattrfunc)%(tp_setattr)s,	/* tp_setattr */\n' \
        '    (cmpfunc)%(tp_compare)s,		/* tp_compare */\n' \
        '    (reprfunc)%(tp_repr)s,		/* tp_repr */\n' \
        '    %(tp_as_number)s,			/* tp_as_number */\n' \
        '    %(tp_as_sequence)s,		/* tp_as_sequence */\n' \
        '    %(tp_as_mapping)s,			/* tp_as_mapping */\n' \
        '    (hashfunc)%(tp_hash)s,		/* tp_hash */\n' \
        '    (ternaryfunc)%(tp_call)s,		/* tp_call */\n' \
        '    (reprfunc)%(tp_str)s,		/* tp_str */\n' \
        '    (getattrofunc)0,			/* tp_getattro */\n' \
        '    (setattrofunc)0,			/* tp_setattro */\n' \
        '    0,					/* tp_as_buffer */\n' \
        '    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */\n' \
        '    NULL, 				/* Documentation string */\n' \
        '    (traverseproc)0,			/* tp_traverse */\n' \
        '    (inquiry)0,			/* tp_clear */\n' \
        '    (richcmpfunc)%(tp_richcompare)s,	/* tp_richcompare */\n' \
        '    %(tp_weaklistoffset)s,             /* tp_weaklistoffset */\n' \
        '    (getiterfunc)%(tp_iter)s,		/* tp_iter */\n' \
        '    (iternextfunc)%(tp_iternext)s,	/* tp_iternext */\n' \
        '    %(tp_methods)s,			/* tp_methods */\n' \
        '    0,					/* tp_members */\n' \
        '    %(tp_getset)s,		       	/* tp_getset */\n' \
        '    NULL,				/* tp_base */\n' \
        '    NULL,				/* tp_dict */\n' \
        '    (descrgetfunc)%(tp_descr_get)s,	/* tp_descr_get */\n' \
        '    (descrsetfunc)%(tp_descr_set)s,	/* tp_descr_set */\n' \
        '    %(tp_dictoffset)s,                 /* tp_dictoffset */\n' \
        '    (initproc)%(tp_init)s,		/* tp_init */\n' \
        '};\n\n'

    slots_list = ['tp_getattr', 'tp_setattr', 'tp_compare', 'tp_repr',
                  'tp_as_number', 'tp_as_sequence', 'tp_as_mapping', 'tp_hash',
                  'tp_call', 'tp_str', 'tp_richcompare', 'tp_iter',
                  'tp_iternext', 'tp_descr_get', 'tp_descr_set', 'tp_init']

    getter_tmpl = \
        'static PyObject *\n' \
        '%(funcname)s(PyObject *self, void *closure)\n' \
        '{\n' \
        '%(varlist)s' \
        '    ret = %(field)s;\n' \
        '%(codeafter)s\n' \
        '}\n\n'
    
    parse_tmpl = \
        '    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "%(typecodes)s:%(name)s"%(parselist)s))\n' \
        '        return %(errorreturn)s;\n'

    deprecated_tmpl = \
        '    if (PyErr_Warn(PyExc_DeprecationWarning, "%(deprecationmsg)s") < 0)\n' \
        '        return %(errorreturn)s;\n'

    methdef_tmpl = '    { "%(name)s", (PyCFunction)%(cname)s, %(flags)s },\n'

    noconstructor = \
        'static int\n' \
        'pygobject_no_constructor(PyObject *self, PyObject *args, PyObject *kwargs)\n' \
        '{\n' \
        '    gchar buf[512];\n' \
        '\n' \
        '    g_snprintf(buf, sizeof(buf), "%s is an abstract widget", self->ob_type->tp_name);\n' \
        '    PyErr_SetString(PyExc_NotImplementedError, buf);\n' \
        '    return -1;\n' \
        '}\n\n'

    function_tmpl = \
        'static PyObject *\n' \
        '_wrap_%(cname)s(PyObject *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    %(setreturn)s%(cname)s(%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '}\n\n'

    # template for method calls
    constructor_tmpl = None
    method_tmpl = None

    def __init__(self, parser, objinfo, overrides, fp=FileOutput(sys.stdout)):
        self.parser = parser
        self.objinfo = objinfo
        self.overrides = overrides
        self.fp = fp

    def get_lower_name(self):
        return string.lower(string.replace(self.objinfo.typecode,
                                           '_TYPE_', '_', 1))

    def get_field_accessor(self, fieldname):
        raise NotImplementedError

    def get_initial_class_substdict(self): return {}

    def get_initial_constructor_substdict(self):
        return { 'name': '%s.__init__' % self.objinfo.c_name,
                 'errorreturn': '-1' }
    def get_initial_method_substdict(self, method):
        return { 'name': '%s.%s' % (self.objinfo.c_name, method.name) }

    def write_class(self):
        self.fp.write('\n/* ----------- ' + self.objinfo.c_name + ' ----------- */\n\n')
        substdict = self.get_initial_class_substdict()
        substdict['typename'] = self.objinfo.c_name
        if self.overrides.modulename:
            substdict['classname'] = '%s.%s' % (self.overrides.modulename,
                                           self.objinfo.name)
        else:
            substdict['classname'] = self.objinfo.name

        substdict['tp_init'] = self.write_constructor()
        substdict['tp_methods'] = self.write_methods()
        substdict['tp_getset'] = self.write_getsets()

        # handle slots ...
        for slot in self.slots_list:
            if substdict.has_key(slot) and substdict[slot] != '0':
                continue
            
            slotname = '%s.%s' % (self.objinfo.c_name, slot)
            slotfunc = '_wrap_%s_%s' % (self.get_lower_name(), slot)
            if slot[:6] == 'tp_as_':
                slotfunc = '&' + slotfunc
            if self.overrides.slot_is_overriden(slotname):
                lineno, filename = self.overrides.getstartline(slotname)
                self.fp.setline(lineno, filename)
                self.fp.write(self.overrides.slot_override(slotname))
                self.fp.resetline()
                self.fp.write('\n\n')
                substdict[slot] = slotfunc
            else:
                substdict[slot] = '0'
    
        self.fp.write(self.type_tmpl % substdict)

    def write_function_wrapper(self, function_obj, template,
                               handle_return=0, is_method=0, kwargs_needed=0,
                               substdict=None):
        '''This function is the guts of all functions that generate
        wrappers for functions, methods and constructors.'''
        if not substdict: substdict = {}
        
        info = argtypes.WrapperInfo()

        substdict.setdefault('errorreturn', 'NULL')

        # for methods, we want the leading comma
        if is_method:
            info.arglist.append('')

        if function_obj.varargs:
            raise ValueError, "varargs functions not supported"

        for ptype, pname, pdflt, pnull in function_obj.params:
            if pdflt and '|' not in info.parsestr:
                info.add_parselist('|', [], [])
            handler = argtypes.matcher.get(ptype)
            handler.write_param(ptype, pname, pdflt, pnull, info)

        substdict['setreturn'] = ''
        if handle_return:
            if function_obj.ret not in ('none', None):
                substdict['setreturn'] = 'ret = '
            handler = argtypes.matcher.get(function_obj.ret)
            handler.write_return(function_obj.ret,
                                 function_obj.caller_owns_return, info)

        if function_obj.deprecated != None:
            deprecated = self.deprecated_tmpl % {
                'deprecationmsg': function_obj.deprecated,
                'errorreturn': substdict['errorreturn'] }
        else:
            deprecated = ''

        # if name isn't set, set it to function_obj.name
        substdict.setdefault('name', function_obj.name)

        if self.objinfo:
            substdict['typename'] = self.objinfo.c_name
        substdict['cname'] = function_obj.c_name
        substdict['varlist'] = info.get_varlist()
        substdict['typecodes'] = info.parsestr
        substdict['parselist'] = info.get_parselist()
        substdict['arglist'] = info.get_arglist()
        substdict['codebefore'] = deprecated + \
            string.replace(info.get_codebefore(),
            'return NULL', 'return ' + substdict['errorreturn'])
        substdict['codeafter'] = string.replace(info.get_codeafter(),
            'return NULL', 'return ' + substdict['errorreturn'])

        if info.parsestr or kwargs_needed:
            substdict['parseargs'] = self.parse_tmpl % substdict
            substdict['extraparams'] = ', PyObject *args, PyObject *kwargs'
            flags = 'METH_VARARGS|METH_KEYWORDS'

            # prepend the keyword list to the variable list
            substdict['varlist'] = info.get_kwlist() + substdict['varlist']
        else:
            substdict['parseargs'] = ''
            substdict['extraparams'] = ''
            flags = 'METH_NOARGS'

        return template % substdict, flags

    def write_constructor(self):
        initfunc = '0'
        constructor = self.parser.find_constructor(self.objinfo,self.overrides)
        if constructor:
            try:
                if self.overrides.is_overriden(constructor.c_name):
                    lineno, filename = self.overrides.getstartline(
                        constructor.c_name)
                    self.fp.setline(lineno, filename)
                    self.fp.write(self.overrides.override(constructor.c_name))
                    self.fp.resetline()
                    self.fp.write('\n\n')
                else:
                    # write constructor from template ...
                    code = self.write_function_wrapper(constructor,
                        self.constructor_tmpl,
                        handle_return=0, is_method=0, kwargs_needed=1,
                        substdict=self.get_initial_constructor_substdict())[0]
                    self.fp.write(code)
                initfunc = '_wrap_' + constructor.c_name
            except:
                sys.stderr.write('Could not write constructor for %s: %s\n' 
                                 % (self.objinfo.c_name, exc_info()))
                # this is a hack ...
                if not hasattr(self.overrides, 'no_constructor_written'):
                    self.fp.write(self.noconstructor)
                    self.overrides.no_constructor_written = 1
                initfunc = 'pygobject_no_constructor'
        else:
            # this is a hack ...
            if not hasattr(self.overrides, 'no_constructor_written'):
                self.fp.write(self.noconstructor)
                self.overrides.no_constructor_written = 1
            initfunc = 'pygobject_no_constructor'
        return initfunc

    def write_methods(self):
        methods = []
        for meth in self.parser.find_methods(self.objinfo):
            if self.overrides.is_ignored(meth.c_name):
                continue
            try:
                methflags = 'METH_VARARGS'
                if self.overrides.is_overriden(meth.c_name):
                    if not self.overrides.is_already_included(meth.c_name):
                        lineno, filename = self.overrides.getstartline(meth.c_name)
                        self.fp.setline(lineno, filename)
                        self.fp.write(self.overrides.override(meth.c_name))
                        self.fp.resetline()
                        self.fp.write('\n\n')
                    if self.overrides.wants_kwargs(meth.c_name):
                        methflags = methflags + '|METH_KEYWORDS'
                    elif self.overrides.wants_noargs(meth.c_name):
                        methflags = 'METH_NOARGS'
                else:
                    # write constructor from template ...
                    code, methflags = self.write_function_wrapper(meth,
                        self.method_tmpl, handle_return=1, is_method=1,
                        substdict=self.get_initial_method_substdict(meth))
                    self.fp.write(code)
                methods.append(self.methdef_tmpl %
                               { 'name':  fixname(meth.name),
                                 'cname': '_wrap_' + meth.c_name,
                                 'flags': methflags})
            except:
                sys.stderr.write('Could not write method %s.%s: %s\n'
                                % (self.objinfo.c_name, meth.name, exc_info()))

        if methods:
            methoddefs = '_Py%s_methods' % self.objinfo.c_name
            # write the PyMethodDef structure
            methods.append('    { NULL, NULL, 0 }\n')
            self.fp.write('static PyMethodDef %s[] = {\n' % methoddefs)
            self.fp.write(string.join(methods, ''))
            self.fp.write('};\n\n')
        else:
            methoddefs = 'NULL'
        return methoddefs
    
    def write_getsets(self):
        lower_name = self.get_lower_name()
        getsets_name = lower_name + '_getsets'
        getterprefix = '_wrap_' + lower_name + '__get_'
        setterprefix = '_wrap_' + lower_name + '__set_'

        # no overrides for the whole function.  If no fields, don't write a func
        if not self.objinfo.fields:
            return '0'
        getsets = []
        for ftype, fname in self.objinfo.fields:
            gettername = '0'
            settername = '0'
            attrname = self.objinfo.c_name + '.' + fname
            if self.overrides.attr_is_overriden(attrname):
                lineno, filename = self.overrides.getstartline(attrname)
                code = self.overrides.attr_override(attrname)
                self.fp.setline(lineno, filename)
                self.fp.write(code)
                self.fp.resetline()
                if string.find(code, getterprefix + fname) >= 0:
                    gettername = getterprefix + fname
                if string.find(code, setterprefix + fname) >= 0:
                    settername = setterprefix + fname
            if gettername == '0':
                try:
                    funcname = getterprefix + fname
                    info = argtypes.WrapperInfo()
                    handler = argtypes.matcher.get(ftype)
                    # for attributes, we don't own the "return value"
                    handler.write_return(ftype, 0, info)
                    self.fp.write(self.getter_tmpl %
                                  { 'funcname': funcname,
                                    'varlist': info.varlist,
                                    'field': self.get_field_accessor(fname),
                                    'codeafter': info.get_codeafter() })
                    gettername = funcname
                except:
                    sys.stderr.write("Could not write getter for %s.%s: %s\n"
                                     % (self.objinfo.c_name, fname, exc_info()))
            if gettername != '0' or settername != '0':
                getsets.append('    { "%s", (getter)%s, (setter)%s },\n' %
                               (fixname(fname), gettername, settername))

        if not getsets:
            return '0'
        self.fp.write('static PyGetSetDef %s[] = {\n' % getsets_name)
        for getset in getsets:
            self.fp.write(getset)
        self.fp.write('    { NULL, (getter)0, (setter)0 },\n')
        self.fp.write('};\n\n')
    
        return getsets_name

    def write_functions(self, prefix):
        self.fp.write('\n/* ----------- functions ----------- */\n\n')
        functions = []
        for func in self.parser.find_functions():
            if self.overrides.is_ignored(func.c_name):
                continue
            try:
                methflags = 'METH_VARARGS'
                if self.overrides.is_overriden(func.c_name):
                    lineno, filename = self.overrides.getstartline(func.c_name)
                    self.fp.setline(lineno, filename)
                    self.fp.write(self.overrides.override(func.c_name))
                    self.fp.resetline()
                    self.fp.write('\n\n')
                    if self.overrides.wants_kwargs(func.c_name):
                        methflags = methflags + '|METH_KEYWORDS'
                    elif self.overrides.wants_noargs(func.c_name):
                        methflags = 'METH_NOARGS'
                else:
                    # write constructor from template ...
                    code, methflags = self.write_function_wrapper(func,
                        self.function_tmpl, handle_return=1, is_method=0)
                    self.fp.write(code)
                functions.append(self.methdef_tmpl %
                                 { 'name':  func.name,
                                   'cname': '_wrap_' + func.c_name,
                                   'flags': methflags })
            except:
                sys.stderr.write('Could not write function %s: %s\n'
                                 % (func.name, exc_info()))
        # write the PyMethodDef structure
        functions.append('    { NULL, NULL, 0 }\n')
        
        self.fp.write('PyMethodDef ' + prefix + '_functions[] = {\n')
        self.fp.write(string.join(functions, ''))
        self.fp.write('};\n\n')

class GObjectWrapper(Wrapper):
    constructor_tmpl = \
        'static int\n' \
        '_wrap_%(cname)s(PyGObject *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    self->obj = (GObject *)%(cname)s(%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '    if (!self->obj) {\n' \
        '        PyErr_SetString(PyExc_RuntimeError, "could not create %(typename)s object");\n' \
        '        return -1;\n' \
        '    }\n' \
        '    pygobject_register_wrapper((PyObject *)self);\n' \
        '    return 0;\n' \
        '}\n\n'
    method_tmpl = \
        'static PyObject *\n' \
        '_wrap_%(cname)s(PyGObject *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    %(setreturn)s%(cname)s(%(cast)s(self->obj)%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '}\n\n'

    def __init__(self, parser, objinfo, overrides, fp=FileOutput(sys.stdout)):
        Wrapper.__init__(self, parser, objinfo, overrides, fp)
        if self.objinfo:
            self.castmacro = string.replace(self.objinfo.typecode,
                                            '_TYPE_', '_', 1)

    def get_initial_class_substdict(self):
        return { 'tp_basicsize'      : 'PyGObject',
                 'tp_weaklistoffset' : 'offsetof(PyGObject, weakreflist)',
                 'tp_dictoffset'     : 'offsetof(PyGObject, inst_dict)' }
    
    def get_field_accessor(self, fieldname):
        castmacro = string.replace(self.objinfo.typecode, '_TYPE_', '_', 1)
        return '%s(pygobject_get(self))->%s' % (castmacro, fieldname)

    def get_initial_constructor_substdict(self):
        substdict = Wrapper.get_initial_constructor_substdict(self)
        return substdict

    def get_initial_method_substdict(self, method):
        substdict = Wrapper.get_initial_method_substdict(self, method)
        substdict['cast'] = string.replace(self.objinfo.typecode, '_TYPE_', '_', 1)
        return substdict

class GInterfaceWrapper(GObjectWrapper):
    def get_initial_class_substdict(self):
        return { 'tp_basicsize'      : 'PyGObject',
                 'tp_weaklistoffset' : '0',
                 'tp_dictoffset'     : '0'}

    def write_constructor(self):
        # interfaces have no constructors ...
        return '0'
    def write_getsets(self):
        # interfaces have no fields ...
        return '0'

class GBoxedWrapper(Wrapper):
    constructor_tmpl = \
        'static int\n' \
        '_wrap_%(cname)s(PyGBoxed *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    self->gtype = %(typecode)s;\n' \
        '    self->free_on_dealloc = FALSE;\n' \
        '    self->boxed = %(cname)s(%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '    if (!self->boxed) {\n' \
        '        PyErr_SetString(PyExc_RuntimeError, "could not create %(typename)s object");\n' \
        '        return -1;\n' \
        '    }\n' \
        '    self->free_on_dealloc = TRUE;\n' \
        '    return 0;\n' \
        '}\n\n'

    method_tmpl = \
        'static PyObject *\n' \
        '_wrap_%(cname)s(PyObject *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    %(setreturn)s%(cname)s(pyg_boxed_get(self, %(typename)s)%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '}\n\n'

    def get_initial_class_substdict(self):
        return { 'tp_basicsize'      : 'PyGBoxed',
                 'tp_weaklistoffset' : '0',
                 'tp_dictoffset'     : '0' }

    def get_field_accessor(self, fieldname):
        return 'pyg_boxed_get(self, %s)->%s' % (self.objinfo.c_name, fieldname)

    def get_initial_constructor_substdict(self):
        substdict = Wrapper.get_initial_constructor_substdict(self)
        substdict['typecode'] = self.objinfo.typecode
        return substdict

class GPointerWrapper(GBoxedWrapper):
    constructor_tmpl = \
        'static int\n' \
        '_wrap_%(cname)s(PyGPointer *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    self->gtype = %(typecode)s;\n' \
        '    self->pointer = %(cname)s(%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '    if (!self->pointer) {\n' \
        '        PyErr_SetString(PyExc_RuntimeError, "could not create %(typename)s object");\n' \
        '        return -1;\n' \
        '    }\n' \
        '    return 0;\n' \
        '}\n\n'

    method_tmpl = \
        'static PyObject *\n' \
        '_wrap_%(cname)s(PyObject *self%(extraparams)s)\n' \
        '{\n' \
        '%(varlist)s' \
        '%(parseargs)s' \
        '%(codebefore)s' \
        '    %(setreturn)s%(cname)s(pyg_pointer_get(self, %(typename)s)%(arglist)s);\n' \
        '%(codeafter)s\n' \
        '}\n\n'

    def get_initial_class_substdict(self):
        return { 'tp_basicsize'      : 'PyGPointer',
                 'tp_weaklistoffset' : '0',
                 'tp_dictoffset'     : '0' }

    def get_field_accessor(self, fieldname):
        return 'pyg_pointer_get(self, %s)->%s' % (self.objinfo.c_name, fieldname)

    def get_initial_constructor_substdict(self):
        substdict = Wrapper.get_initial_constructor_substdict(self)
        substdict['typecode'] = self.objinfo.typecode
        return substdict

def write_enums(parser, prefix, fp=sys.stdout):
    if not parser.enums:
        return
    fp.write('\n/* ----------- enums and flags ----------- */\n\n')
    fp.write('void\n' + prefix + '_add_constants(PyObject *module, const gchar *strip_prefix)\n{\n')
    for enum in parser.enums:
        if enum.typecode is None:
            for nick, value in enum.values:
                fp.write('    PyModule_AddIntConstant(module, pyg_constant_strip_prefix("%s", strip_prefix), %s);\n'
                         % (value, value))
        else:
            if enum.deftype == 'enum':
                fp.write('    pyg_enum_add_constants(module, %s, strip_prefix);\n'
                         % (enum.typecode,))
            else:
                fp.write('    pyg_flags_add_constants(module, %s, strip_prefix);\n'
                         % (enum.typecode,))
    fp.write('}\n\n')

def write_source(parser, overrides, prefix, fp=FileOutput(sys.stdout)):
    fp.write('/* -*- Mode: C; c-basic-offset: 4 -*- */\n\n')
    fp.write('#include <Python.h>\n\n\n')
    fp.write(overrides.get_headers())
    fp.resetline()
    fp.write('\n\n')
    fp.write('/* ---------- types from other modules ---------- */\n')
    for module, pyname, cname in overrides.get_imports():
        fp.write('static PyTypeObject *_%s;\n' % cname)
        fp.write('#define %s (*_%s)\n' % (cname, cname))
    fp.write('\n\n')
    fp.write('/* ---------- forward type declarations ---------- */\n')
    for obj in parser.boxes:
        fp.write('PyTypeObject Py' + obj.c_name + '_Type;\n')
    for obj in parser.objects:
        fp.write('PyTypeObject Py' + obj.c_name + '_Type;\n')
    for interface in parser.interfaces:
        fp.write('PyTypeObject Py' + interface.c_name + '_Type;\n')
    fp.write('\n')
    
    for boxed in parser.boxes:
        wrapper = GBoxedWrapper(parser, boxed, overrides, fp)
        wrapper.write_class()
        fp.write('\n')
    for pointer in parser.pointers:
        wrapper = GPointerWrapper(parser, pointer, overrides, fp)
        wrapper.write_class()
        fp.write('\n')
    for obj in parser.objects:
        wrapper = GObjectWrapper(parser, obj, overrides, fp)
        wrapper.write_class()
        fp.write('\n')
    for interface in parser.interfaces:
        wrapper = GInterfaceWrapper(parser, interface, overrides, fp)
        wrapper.write_class()
        fp.write('\n')

    wrapper = Wrapper(parser, None, overrides, fp)
    wrapper.write_functions(prefix)

    write_enums(parser, prefix, fp)

    fp.write('/* intialise stuff extension classes */\n')
    fp.write('void\n' + prefix + '_register_classes(PyObject *d)\n{\n')
    imports = overrides.get_imports()[:]
    if imports:
        bymod = {}
        for module, pyname, cname in imports:
            bymod.setdefault(module, []).append((pyname, cname))
        fp.write('    PyObject *module;\n\n')
        for module in bymod:
            fp.write('    if ((module = PyImport_ImportModule("%s")) != NULL) {\n' % module)
            fp.write('        PyObject *moddict = PyModule_GetDict(module);\n\n')
            for pyname, cname in bymod[module]:
                fp.write('        _%s = (PyTypeObject *)PyDict_GetItemString(moddict, "%s");\n' % (cname, pyname))
            fp.write('    } else {\n')
            fp.write('        Py_FatalError("could not import %s");\n' %module)
            fp.write('        return;\n')
            fp.write('    }\n')
        fp.write('\n')
    fp.write(overrides.get_init() + '\n')
    fp.resetline()

    for boxed in parser.boxes:
        fp.write('    pyg_register_boxed(d, "' + boxed.name +
                 '", ' + boxed.typecode + ', &Py' + boxed.c_name + '_Type);\n')
    for pointer in parser.pointers:
        fp.write('    pyg_register_pointer(d, "' + pointer.name +
                 '", ' + pointer.typecode + ', &Py' + pointer.c_name + '_Type);\n')
    for interface in parser.interfaces:
        fp.write('    pyg_register_interface(d, "' + interface.name +
                 '", '+ interface.typecode + ', &Py' + interface.c_name +
                 '_Type);\n')
    objects = parser.objects[:]
    pos = 0
    while pos < len(objects):
        parent = objects[pos].parent
        for i in range(pos+1, len(objects)):
            if objects[i].c_name == parent:
                objects.insert(i+1, objects[pos])
                del objects[pos]
                break
        else:
            pos = pos + 1
    for obj in objects:
        bases = []
        if obj.parent != None:
            bases.append(obj.parent)
        bases = bases + obj.implements
        if bases:
            fp.write('    pygobject_register_class(d, "' + obj.c_name +
                     '", ' + obj.typecode + ', &Py' + obj.c_name +
                     '_Type, Py_BuildValue("(' + 'O' * len(bases) + ')", ' +
                     string.join(map(lambda s: '&Py'+s+'_Type', bases), ', ') +
                     '));\n')
        else:
            fp.write('    pygobject_register_class(d, "' + obj.c_name +
                     '", ' + obj.typecode + ', &Py' + obj.c_name +
                     '_Type, NULL);\n')
    fp.write('}\n')

def register_types(parser):
    for boxed in parser.boxes:
        argtypes.matcher.register_boxed(boxed.c_name, boxed.typecode)
    for pointer in parser.pointers:
        argtypes.matcher.register_pointer(pointer.c_name, pointer.typecode)
    for obj in parser.objects:
        argtypes.matcher.register_object(obj.c_name, obj.parent, obj.typecode)
    for obj in parser.interfaces:
        argtypes.matcher.register_object(obj.c_name, None, obj.typecode)
    for enum in parser.enums:
	if enum.deftype == 'flags':
	    argtypes.matcher.register_flag(enum.c_name, enum.typecode)
	else:
	    argtypes.matcher.register_enum(enum.c_name, enum.typecode)

def main():
    o = override.Overrides()
    prefix = 'pygtk'
    outfilename = None
    errorfilename = None
    opts, args = getopt.getopt(sys.argv[1:], "o:p:r:t:",
                        ["override=", "prefix=", "register=", "outfilename=",
                         "load-types=", "errorfilename="])
    for opt, arg in opts:
        if opt in ('-o', '--override'):
            o = override.Overrides(arg)
        elif opt in ('-p', '--prefix'):
            prefix = arg
        elif opt in ('-r', '--register'):
            p = defsparser.DefsParser(arg)
            p.startParsing()
            register_types(p)
            del p
        elif opt == '--outfilename':
            outfilename = arg
        elif opt == '--errorfilename':
            errorfilename = arg
        elif opt in ('-t', '--load-types'):
            globals = {}
            execfile(arg, globals)
    if len(args) < 1:
        sys.stderr.write(
            'usage: codegen.py [-o overridesfile] [-p prefix] defsfile\n')
        sys.exit(1)
    if errorfilename:
        sys.stderr = open(errorfilename, "w")
    p = defsparser.DefsParser(args[0])
    if not outfilename:
        outfilename = os.path.splitext(args[0])[0] + '.c'
    p.startParsing()
    register_types(p)
    write_source(p, o, prefix, FileOutput(sys.stdout, outfilename))

if __name__ == '__main__':
    main()
