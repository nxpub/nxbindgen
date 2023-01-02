INCLUDES = [
    'Python.h',
    'pycore_abstract.h',      # _PyIndex_Check()
    'pycore_call.h',          # _PyObject_FastCallDictTstate()
    'pycore_ceval.h',         # _PyEval_SignalAsyncExc()
    'pycore_code.h',
    'pycore_function.h',
    'pycore_long.h',          # _PyLong_GetZero()
    'pycore_object.h',        # _PyObject_GC_TRACK()
    'pycore_moduleobject.h',  # PyModuleObject
    'pycore_opcode.h',        # EXTRA_CASES
    'pycore_pyerrors.h',      # _PyErr_Fetch()
    'pycore_pymem.h',         # _PyMem_IsPtrFreed()
    'pycore_pystate.h',       # _PyInterpreterState_GET()
    'pycore_range.h',         # _PyRangeIterObject
    'pycore_sliceobject.h',   # _PyBuildSlice_ConsumeRefs
    'pycore_sysmodule.h',     # _PySys_Audit()
    'pycore_tuple.h',         # _PyTuple_ITEMS()
    'pycore_emscripten_signal.h',  # _Py_CHECK_EMSCRIPTEN_SIGNALS
    'pycore_dict.h',
    'dictobject.h',
    'pycore_frame.h',
    'opcode.h',
    'pydtrace.h',
    'setobject.h',
    'structmember.h',         # struct PyMemberDef, T_OFFSET_EX
]

DEFINES = {
    # Stack effect macros
    'SET_TOP(v)': '(env.stack.set_top(v))',
    'SET_SECOND(v)': '(env.stack.set_second(v))',
    'PEEK(n)': '(env.stack.peek(n))',
    'POKE(n, v)': '(env.stack.poke(n, v))',
    'PUSH(val)': '(env.stack.push(val))',
    'POP()': '(env.stack.pop())',
    'TOP()': '(env.stack.top())',
    'SECOND()': '(env.stack.second())',
    'STACK_GROW(n)': '(env.stack.grow(n))',
    'STACK_SHRINK(n)': '(env.stack.shrink(n))',
    'EMPTY()': '(env.stack.is_empty())',
    'STACK_LEVEL()': '(env.stack.level())',
    # Local variable macros
    'GETLOCAL(i)': '(env.frame.get_local(i))',
    'SETLOCAL(i, val)': '(env.frame.set_local(i, val))',
    'GETITEM(src, i)': '(env.frame.get_item(src, i))',
    # Flow control macros
    'DEOPT_IF(cond, instname)': '(env.flow.deopt_if(cond, #instname))',
    'ERROR_IF(cond, labelname)': '(env.flow.error_if(cond, #labelname))',
    'JUMPBY(offset)': '(env.flow.jumpby(offset))',
    'NEXTOPARG()': '(env.flow.next_oparg())',
    'GO_TO_INSTRUCTION(instname)': '(env.flow.go_to_inst(instname))',
    'DISPATCH_SAME_OPARG()': '(env.flow.dispatch_same_oparg())',
    'TRACE_FUNCTION_EXIT()': '(env.flow.trace_function_exit())',
    'DTRACE_FUNCTION_EXIT()': '(env.flow.dtrace_function_exit())',
    'PREDICTED(name)': '(env.flow.predicted(#name))',
    'PREDICT(name)': '(env.flow.predict(#name))',
    'STAT_INC(name, type)': '(env.flow.stat_inc(#name, #type))',
    'DISPATCH()': '(env.flow.dispatch())',
    'PRE_DISPATCH_GOTO()': '(env.flow.pre_dispatch_goto())',
    'DISPATCH_GOTO()': '(env.flow.dispatch_goto())',
    'DISPATCH_INLINED': '(env.flow.dispatch_inlined())',
    # Memory related
    'Py_INCREF(val)': '(env.memory.inc_ref(val))',
    'Py_DECREF(val)': '(env.memory.dec_ref(val))',
    'Py_SETREF(dst, src)': '(env.memory.set_ref(dst, src))',
    'Py_XSETREF(dst, src)': '(env.memory.set_ref(dst, src))',
    'Py_CLEAR(op)': '(env.memory.clear(op))',
    '_Py_DECREF_SPECIALIZED(val, func)': '(env.memory.dec_ref_spec(val, func))',
    '_Py_DECREF_NO_DEALLOC(val)': '(env.memory.dec_ref_no_dealloc(val))',
    # Special
    'TARGET(name)': 'void op_##name(env)',
    'def': '_def',  # TODO: this is a bad idea
    'from': '_from',
    'NULL': 'None',
    '_Py_TrueStruct': 'True',
    '_Py_FalseStruct': 'False',
}
