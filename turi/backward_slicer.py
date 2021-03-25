import logging

from queue import Queue

from .statements import *
from .utils import walk_all_blocks

logging.basicConfig()
log = logging.getLogger('BackwardSlicer')
log.setLevel(logging.DEBUG)


class BackwardSlicerError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class BackwardSlicer:
    """
        Backward Slicer: staring from some input, go back to code paths that
        affect the input
    """
    MAX_ITER = 5000
    MAX_ITERS_BLOCK = 30

    def __init__(self, project, max_iter=None):
        self.project = project
        if max_iter:
            self.MAX_ITER = max_iter
        self.iters_per_block = {}
        self.affected_blocks = set()
        self._tainted = {}
        self._input_data = None
        self._input = None

    @property
    def input_blocks(self):
        if self._input_data:
            return [input_block for input_block, _, _ in self._input_data]
        else:
            return []

    def tainted_in_block(self, block):
        return self._tainted[block][self.project.blocks_to_methods[block]]

    def tainted_in_method(self, method):
        try:
            return set.union(*[self._tainted[b][method] for b in method.blocks
                               if b in self._tainted and method in self._tainted[b]])
        except:
            return set()

    def _merge_tainted(self, curr_block, prev_block):
        curr_tainted = self._tainted[curr_block]

        if prev_block in self._tainted:
            # time to merge
            prev_tainted = self._tainted[prev_block]
            new_tainted = dict([(m, s) for (m, s) in prev_tainted.items() if m not in curr_tainted])
            new_tainted.update(dict([(m, s) for (m, s) in curr_tainted.items() if m not in prev_tainted]))
            new_tainted.update(dict([(m, s.union(curr_tainted[m])) for (m, s) in prev_tainted.items() if m in curr_tainted]))
            return new_tainted

        return curr_tainted

    def slice(self, input, input_data=None):
        self._input = input
        if not input_data:
            self._input_data = self.locate_input()
        else:
            self._input_data = input_data

        for input_block, var, input_stmt_index in self._input_data:
            # traverse CFG
            queue = Queue()
            queue.put(input_block)
            iterations = 0
            visited = set()
            tainted_input = {self.project.blocks_to_methods[input_block]: set([var])}
            self._tainted[input_block] = tainted_input
            self.affected_blocks.add(input_block)

            while not queue.empty() and iterations < self.MAX_ITER:
                curr_block = queue.get()
                curr_method = self.project.blocks_to_methods[curr_block]
                iterations += 1

                if curr_block in visited:
                    if curr_block not in self.iters_per_block:
                        self.iters_per_block[curr_block] = 0
                    self.iters_per_block[curr_block] += 1

                    iters_curr_block = self.iters_per_block[curr_block]
                    if iters_curr_block >= self.MAX_ITERS_BLOCK:
                        continue
                else:
                    visited.add(curr_block)

                # get variable to follow for this block
                curr_tainted = self._tainted[curr_block].get(curr_method, [])

                if curr_block == input_block:
                    # if curr_block is the input one, we don't want to consider
                    # statements after the assignment of the tainted var
                    stmt_index = input_stmt_index + 1
                    num_statements = len(curr_block.statements[:stmt_index])
                else:
                    # otherwise consider all the statements in the block
                    stmt_index = None
                    num_statements = len(curr_block.statements)

                # better work at the statement granularity?
                for i in range(num_statements):
                    # Get statements that use the tainted vars
                    set_stmts = self.get_set_stmts(curr_block,
                                                   curr_tainted,
                                                   stmt_index=stmt_index)

                    if set_stmts:
                        self.affected_blocks.add(curr_block)
                        # Get the list of variables used in the assignment statements
                        # which involve one or more tainted variables.
                        # Also, get the list of assignment statements those assign
                        # the return values of function calls (rvalue) to variables (lvalue)
                        new_use, new_call_use = self.get_use(set_stmts)
                        for use_var in new_use:
                            self._tainted[curr_block][curr_method].add(use_var)

                        # Get a list of the return values and corresponding blocks 
                        # of the functions which have their return values assigned to
                        # variables living in the current scope. Iterate over this list.
                        for ret_block, ret_var in self.get_call_ret(new_call_use):
                            called_m = self.project.blocks_to_methods[ret_block]
                            if ret_block not in self._tainted:
                                self._tainted[ret_block] = {}
                            if called_m not in self._tainted[ret_block]:
                                self._tainted[ret_block][called_m] = set()
                            self._tainted[ret_block][called_m].add(ret_var)
                            queue.put(ret_block)

                    # $r3.<init>($r7)
                    # $r3 is tainted, we want to taint $r7
                    # Get the tainted arguments (variables); given that the objects
                    # the functions are called on are tainted themselves
                    call_taints = self.get_call_taints(curr_block,
                                                       curr_tainted,
                                                       stmt_index=stmt_index)

                    if call_taints:
                        self.affected_blocks.add(curr_block)
                        for var_name in call_taints:
                            self._tainted[curr_block][curr_method].add(var_name)

                curr_tainted = self._tainted[curr_block].get(curr_method, [])

                for call_method, var_name in self.tainted_params(curr_block, curr_tainted):
                    if call_method not in self._tainted[curr_block]:
                        self._tainted[curr_block][call_method] = set()
                    self._tainted[curr_block][call_method].add(var_name)

                for prev_block in self.project.cfgfull().get_prev_blocks(curr_block):
                    queue.put(prev_block)
                    self._tainted[prev_block] = self._merge_tainted(curr_block, prev_block)

    def locate_input(self):
        res = []

        if self._input['type'] == 'method_var':
            in_cls_name = self._input['class_name']
            in_m_name = self._input['method_name']
            in_m_params = self._input['method_params']
            in_var_name = self._input['var_name']

            for m in self.project.classes[in_cls_name].methods:
                if (in_m_name, tuple(in_m_params)) == (m.name, m.params):
                    for block in m.blocks:
                        for i, stmt in enumerate(block.statements):
                            if is_assign(stmt):
                                if hasattr(stmt.left_op, 'name') and stmt.left_op.name == in_var_name:
                                    res.append((block, stmt.left_op.name, i))

                            elif is_identity(stmt):
                                if hasattr(stmt.left_op, 'name') and stmt.left_op.name == in_var_name:
                                    res.append((block, stmt.left_op.name, i))

        elif self._input['type'] == 'object_field':
            in_cls_name = self._input['class_name']
            in_m_name = self._input['method_name']
            in_m_params = tuple(self._input['method_params'])
            in_obj_class = self._input['obj_class_name']
            in_obj_field = self._input['obj_field_name']

            field = (in_obj_field, in_obj_class)

            try:
                method = self.project.methods[(in_cls_name, in_m_name, in_m_params)]

                for block in method.blocks:
                    for i, stmt in enumerate(block.statements):
                        if is_assign(stmt) or is_identity(stmt):
                            left_op = stmt.left_op
                            if is_instance_field_ref(left_op) and left_op.field == field:
                                # TODO here you should consider also the class
                                # res.append((block, left_op.field[0], i))

                                # TODO very bad code. Please, don't judge me for this
                                if is_local_var(stmt.right_op):
                                    self._input = {'type': 'method_var',
                                                   'class_name': in_cls_name,
                                                   'method_name': in_m_name,
                                                   'method_params': in_m_params,
                                                   'var_name': stmt.right_op.name}
                                    res.extend(self.locate_input())

                                else:
                                    raise NotImplementedError('Field assigned from non var')

            except KeyError:
                log.warning('Input method not found')

        return res

    def get_set_stmts(self, block, vars, stmt_index=None):
        """
            Given a block and a list of "variable" names,
            returns the list of statements that set that variables
        """
        res = []

        for var in vars:
            if stmt_index:
                var_res = self.get_set_var_stmts(block.statements[:stmt_index], var)
            else:
                var_res = self.get_set_var_stmts(block.statements, var)
            res.extend(var_res)

        return res

    def get_call_taints(self, block, vars, stmt_index=None):
        """
            Given a block and a list of variables,
            returns the list of arguments of the functions
            called from the block and invoked on those variables
            # $r3.<init>($r7)
            # $r3 is tainted, we want to taint $r7
            If $r3 is in `vars`, $r7 will be returned
        """
        res = []

        if stmt_index:
            stmts = block.statements[:stmt_index]
        else:
            stmts = block.statements

        for stmt in stmts:
            if is_invoke(stmt) and not is_assign(stmt):
                invoke_expr = stmt.invoke_expr
                if hasattr(invoke_expr, 'base'):
                    if invoke_expr.base.name in vars:
                        for arg in invoke_expr.args:
                            if hasattr(arg, 'name'):
                                res.append(arg.name)

                for arg in invoke_expr.args:
                    if hasattr(arg, 'name'):
                        if arg.name in vars:
                            if hasattr(invoke_expr, 'base'):
                                res.append(invoke_expr.base.name)

        return res

    def get_call_ret(self, call_stmts):
        """
            Given a list of call statements, returns the list of tuples consisting of
            return values from the called functions and the corresponding blocks
        """
        res = []

        for stmt in call_stmts:
            cls_name = stmt.right_op.class_name
            method_name = stmt.right_op.method_name
            method_params = stmt.right_op.method_params

            try:
                method = self.project.methods[(cls_name, method_name, method_params)]
            except KeyError as e:
                # external methods are not supported
                return []

            container_m = self.project.blocks_to_methods[self.project.stmts_to_blocks[stmt]]
            targets = self.project.hierarchy().resolve_invoke(stmt.right_op, method, container_m)

            for target in targets:
                for block in target.blocks:
                    for stmt in block.statements:
                        # Return statement
                        if is_ret(stmt) and hasattr(stmt, 'value'):
                            if hasattr(stmt.value, 'name'):
                                res.append((block, stmt.value.name))

        return res

    def tainted_params(self, block, vars):
        res = []

        for stmt in block.statements:
            if hasattr(stmt, 'right_op') and is_param_ref(stmt.right_op):
                if stmt.left_op.name in vars:
                    index = stmt.right_op.index
                    method = self.project.blocks_to_methods[block]
                    prevs = self.project.callgraph().prev(method)

                    for prev in prevs:
                        calls = self.get_method_calls(prev, method)

                        for call in calls:
                            if hasattr(call, 'invoke_expr'):
                                invoke_expr = call.invoke_expr

                            else:
                                invoke_expr = call.right_op

                            arg = invoke_expr.args[index]
                            if hasattr(arg, 'name'):
                                res.append((prev, arg.name))

        return res

    def get_method_calls(self, caller, called):
        stmts = []

        for block in caller.blocks:
            for stmt in block.statements:
                if is_invoke(stmt):
                    if hasattr(stmt, 'invoke_expr'):
                        invoke_expr = stmt.invoke_expr

                    else:
                        invoke_expr = stmt.right_op

                    cls_name = invoke_expr.class_name
                    method_name = invoke_expr.method_name
                    method_params = invoke_expr.method_params

                    try:
                        method = self.project.methods[(cls_name, method_name, method_params)]
                    except KeyError as e:
                        # skip calls to external methods
                        continue

                    targets = self.project.hierarchy().resolve_invoke(invoke_expr, method, caller)

                    if called in targets:
                        stmts.append(stmt)

        return stmts

    # TODO nested levels
    # num functions to go inside (context level)
    # data flow inside to taint only correct param
    def get_use(self, statements):
        """
            Given a block and a list of statements,
            returns the list of variables used in those statements.
            Also, returns the list of assignment statements that
            assign the return value of a function call
        """
        var_used = set()
        call_ret_used = set()

        for stmt in statements:
            # handle the different use scenarios
            if is_assign(stmt) and is_invoke(stmt.right_op):
                invoke_expr = stmt.right_op

                if hasattr(invoke_expr, 'base'):
                    # --- use object method
                    # --- e.g., new = var.method()
                    # taint method
                    # TODO should we taint the "this"?
                    var_used.add(stmt.right_op.base.name)

                # params
                for arg in invoke_expr.args:
                    if hasattr(arg, 'name'):
                        var_used.add(arg.name)

                call_ret_used.add(stmt)

            elif is_assign(stmt):
                right_op = stmt.right_op
                if is_binop_expr(right_op):
                    # --- binary operation
                    # --- e.g., new = var + other
                    if hasattr(right_op.value1, 'name'):
                        var_used.add(right_op.value1.name)
                    if hasattr(right_op.value2, 'name'):
                        var_used.add(right_op.value2.name)

                elif is_cast_expr(right_op):
                    # --- casting
                    # --- e.g., new = (Object) var
                    if hasattr(right_op.value, 'name'):
                        var_used.add(right_op.value.name)

                elif is_local_var(right_op):
                    # --- simply assignment
                    # --- e.g., new = var
                    var_used.add(right_op.name)

                elif is_instance_field_ref(right_op):
                    # --- assignment from obj field
                    # --- e.g., new = obj.var
                    if hasattr(right_op, 'base'):
                        if hasattr(right_op.base, 'name'):
                            var_used.add(right_op.base.name)
                    var_used.add(right_op.field[0])

                elif is_phi_expr(right_op):
                    # --- assignment from Phi expression
                    # --- e.g., new = Phi(x, var, y)
                    for value, _ in right_op.values:
                        if hasattr(value, 'name'):
                            var_used.add(value.name)
                elif is_static_field_ref(right_op):
                    if hasattr(right_op, 'field'):
                        var_used.add(right_op.field)
            elif is_identity(stmt):
                # --- if 'this' is in the backward slice, add the type of 'this'
                if hasattr(stmt, 'right_op'):
                    if hasattr(stmt.right_op, 'type'):
                        var_used.add(stmt.right_op.type)

            # TODO handle this case in the get_set
            # "enter" in the method
            # elif is_invoke(stmt):
            #     taint = False
            #     # --- param in method, no assignment
            #     # --- e.g., method(var)
            #     invoke_expr = stmt.invoke_expr
            #     for index, arg in enumerate(invoke_expr.args):
            #         if hasattr(arg, 'name'):
            #             if arg.name == var:
            #                 calls.append((stmt, index))
            #                 taint = True

            #     # --- e.g., obj.method(var)
            #     #           taint obj
            #     if taint and hasattr(invoke_expr, 'base'):
            #         if hasattr(invoke_expr.base, 'name'):
            #             assigns.append(stmt)

        return var_used, call_ret_used

    def get_conditional_stmts(self, block, vars):
        target_blocks = []
        cond_stmts = []

        method = self.project.blocks_to_methods[block]

        for var in vars:
            for stmt in block.statements:
                if is_switch(stmt) and hasattr(stmt.key, 'name'):
                    if stmt.key.name == var:
                        cond_stmts.append(stmt)

                        label = stmt.default_target
                        target_block = method.block_by_label[label]
                        target_blocks.append(target_block)
                        labels = stmt.lookup_values_and_targets.values()

                        # switch targets
                        for label in labels:
                            target_block = method.block_by_label[label]
                            target_blocks.append(target_block)

                elif is_condition(stmt):
                    condition = stmt.condition
                    if hasattr(condition, 'value'):
                        if hasattr(condition.value, 'name'):
                            if condition.value.name == var:
                                cond_stmts.append(stmt)

                    if hasattr(condition, 'value1'):
                        if hasattr(condition.value1, 'name'):
                            if condition.value1.name == var:
                                cond_stmts.append(stmt)

                    if hasattr(condition, 'value2'):
                        if hasattr(condition.value2, 'name'):
                            if condition.value2.name == var:
                                cond_stmts.append(stmt)

        return cond_stmts, target_blocks

    def get_set_var_stmts(self, stmts, var):
        """
            Given a list of statements and a "variable" name,
            returns the list of statements that set that variable
        """
        res = []

        for stmt in stmts:
            if is_assign(stmt):
                if hasattr(stmt.left_op, 'name') and stmt.left_op.name == var:
                    res.append(stmt)

                elif is_instance_field_ref(stmt.left_op):
                    # TODO you should consider the field's class!
                    # this is currently imprecise:
                    #   fields with same name (from diff objs) are tainted
                    if stmt.left_op.field[0] == var:
                        res.append(stmt)

                elif is_array_ref(stmt.left_op):
                    if hasattr(stmt.left_op, 'base'):
                        base = stmt.left_op.base
                        if hasattr(base, 'name') and base.name == var:
                            res.append(stmt)

            # we need this for 'this'
            if is_identity(stmt):
                if hasattr(stmt.left_op, 'name') and stmt.left_op.name == var:
                    res.append(stmt)
        return res

    def get_set(self, block, stmts):
        """
            Given a block and list of statements,
            returns the list of variables set in those statements
        """
        var_sets = set()

        method = self.project.blocks_to_methods[block]

        for stmt in stmts:
            if is_assign(stmt):
                if hasattr(stmt.left_op, 'name'):
                    var_sets.add((stmt.left_op.name, method))

                elif hasattr(stmt.left_op, 'base'):
                    if hasattr(stmt.left_op.base, 'name'):
                        var_sets.add((stmt.left_op.base.name, method))

            if is_invoke(stmt):
                if hasattr(stmt, 'invoke_expr'):
                    invoke_expr = stmt.invoke_expr
                    if hasattr(invoke_expr, 'base'):
                        if hasattr(invoke_expr.base, 'name'):
                            var_sets.add((invoke_expr.base.name, method))
                else:
                    invoke_expr = stmt.right_op
                    # we taint the obj even if the method returns
                    # is this OK?
                    # --- x = obj.method(var)
                    if hasattr(invoke_expr, 'base'):
                        if hasattr(invoke_expr.base, 'name'):
                            var_sets.add((invoke_expr.base.name, method))

            if is_condition(stmt):
                # TODO basic condition
                if hasattr(stmt.condition.value1, 'name'):
                    var_sets.add((stmt.condition.value1.name, method))
                elif hasattr(stmt.condition.value2, 'name'):
                    var_sets.add((stmt.condition.value2.name, method))

        return var_sets

    def get_calls_set(self, stmts):
        res = set()

        for stmt, index in stmts:
            if hasattr(stmt, 'invoke_expr'):
                invoke_expr = stmt.invoke_expr

            else:
                invoke_expr = stmt.right_op

            cls_name = invoke_expr.class_name
            method_name = invoke_expr.method_name
            method_params = invoke_expr.method_params

            if cls_name not in self.project.classes:
                # Don't follow vars in calls to methods in libraries
                continue

            method = self.project.methods[(cls_name, method_name, method_params)]
            # TODO here you have to consider Hierarchy
            var_name = None
            # Assumption: Params are defined in the first block
            try:
                for stmt in method.blocks[0].statements:
                    if hasattr(stmt, 'right_op') and is_param_ref(stmt.right_op):
                        if stmt.right_op.index == index:
                            var_name = stmt.left_op.name
            except IndexError:
                pass

            if not var_name:
                # TODO fix this by considering Hierarchy
                pass
                # raise ForwardSlicerError('Tainted parameter not found')
            else:
                res.add((var_name, method))

        return res

    def get_fields_set(self, stmts):
        """
            Given a list of statements,
            returns the list of fields set in those statements
        """
        field_sets = set()

        for stmt in stmts:
            if is_assign(stmt):
                if is_instance_field_ref(stmt.left_op):
                    field_name, class_name = stmt.left_op.field
                    if class_name not in self.project.classes:
                        continue
                    cls = self.project.classes[class_name]
                    # TODO here you have to consider Hierarchy
                    # TODO this doesn't cover obj fields accessed
                    # out of the class methods:
                    # e.g., Object o = new Object()
                    #       o.field = x;
                    #       y = o.field
                    for method in cls.methods:
                        field_sets.add((field_name, method))

        return field_sets
