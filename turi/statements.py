"""
    Utils functions to deal with statements
"""


def is_invoke(stmt):
    if 'invokeexpr' in str(type(stmt)).lower():
        return True

    elif hasattr(stmt, 'invoke_expr'):
        return True

    elif hasattr(stmt, 'right_op'):
        if 'invoke' in str(type(stmt.right_op)).lower():
            return True

    return False


def is_condition(stmt):
    if hasattr(stmt, 'condition'):
        return True

    return False


def is_jump(stmt):
    if 'GotoStmt' in str(type(stmt)):
        return True

    return False


def is_ret(stmt):
    # Return statement
    if 'ReturnStmt' in str(type(stmt)):
        return True

    # Return Void statement
    elif 'ReturnVoidStmt' in str(type(stmt)):
        return True

    return False


def is_switch(stmt):
    if 'TableSwitchStmt' in str(type(stmt)):
        return True

    elif 'LookupSwitchStmt' in str(type(stmt)):
        return True

    return False


def is_assign(stmt):
    if 'AssignStmt' in str(type(stmt)):
        return True

    return False


def is_binop_expr(stmt):
    if 'SootBinopExpr' in str(type(stmt)):
        return True

    return False


def is_param_ref(stmt):
    if 'ParamRef' in str(type(stmt)):
        return True

    return False


def is_cast_expr(stmt):
    if 'CastExpr' in str(type(stmt)):
        return True

    return False


def is_local_var(stmt):
    if 'SootLocal' in str(type(stmt)):
        return True

    return False


def is_instance_field_ref(stmt):
    if 'InstanceFieldRef' in str(type(stmt)):
        return True

    return False

def is_static_field_ref(stmt):
    if 'StaticFieldRef' in str(type(stmt)):
        return True

    return False


def is_phi_expr(stmt):
    if 'SootPhiExpr' in str(type(stmt)):
        return True

    return False


def is_array_ref(stmt):
    if 'ArrayRef' in str(type(stmt)):
        return True

    return False


def is_len_expr(stmt):
    if 'LengthExpr' in str(type(stmt)):
        return True

    return False


def is_identity(stmt):
    if 'IdentityStmt' in str(type(stmt)):
        return True

    return False
