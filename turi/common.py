"""
    Common functions
"""

from collections import namedtuple

from .utils import walk_all_statements
from .statements import *


XRef = namedtuple('XRef', ['cls', 'method', 'stmt', 'type'])


def get_ast_leafs(st):
    def _get_ast_leafs_core(st, leafs=[]):
        ops = ('right_op', 'left_op', 'value', 'value1', 'value2', 'condition')
        for f in [o for o in ops if hasattr(st, o)]:
            _get_ast_leafs_core(getattr(st, f), leafs)
        leafs.append(st)
    leafs = []
    _get_ast_leafs_core(st, leafs)
    return leafs


def is_write_access(st, var):
    if hasattr(st, 'left_op'):
        if any([x == var for x in get_ast_leafs(st.left_op)]):
            return True
    return False


def x_ref(thing, tp, p):
    """
    Find cross-references to a Java entity
    :param thing: a method, a class, a method variable or a class variable
    :param tp: thing type: method, class_var, method_var
    :param classes: the package classes where to search for x-refs
    :return: x-refs
    """

    methods = None
    var_name = None
    cls_name = None
    str_thing = ''
    x_refs = []

    if tp == 'method_var':
        assert type(thing) == list and len(thing) == 4, \
            "local variables should be passed as [class, fun, params, var]"
        thing[2] = tuple(thing[2])
        methods = [p.methods[tuple(thing[:3])]]
        cls_name = thing[0]
        var_name = thing[3]
    elif tp == 'class_var':
        assert type(thing) == list and len(thing) == 2, \
            "class variables should be passed as [class, var]"
        cls_name = thing[0]
        var_name = thing[1]
    elif tp == 'method':
        assert type(thing) == list and len(thing) == 3, \
            "methods should be passed as [class, fun, params]"
        str_thing = '.'.join(thing[:2]) + str(tuple(thing[2])).replace(',)',')').replace('\'', '')
    else:
        return

    for cls, method, st in walk_all_statements(p.classes, methods=methods):
        # method invocations
        if is_invoke(st):
            if tp == 'method':
                if str_thing in str(st):
                    x_refs.append(XRef(cls, method, st, 'read'))
            else:
                # variables
                expr = st.invoke_expr if hasattr(st, 'invoke_expr') else st.right_op
                if any([var_name == a.name and a.type == cls_name for a in expr.args if
                        hasattr(a, 'name')]):
                    x_refs.append(XRef(cls, method, st, 'read'))
        else:
            for leaf in get_ast_leafs(st):
                access = 'write' if is_write_access(st, leaf) else 'read'

                if hasattr(leaf, 'name') and hasattr(leaf, 'type') and \
                                leaf.type == cls_name and leaf.name == var_name:
                    x_refs.append(XRef(cls, method, st, access))

                if hasattr(leaf, 'field') and leaf.field[0] == var_name and leaf.field[1] == cls_name:
                    x_refs.append(XRef(cls, method, st, access))

    return x_refs

