import logging

from queue import Queue

from .statements import *
from .utils import walk_all_blocks

logging.basicConfig()
log = logging.getLogger('ForwardSlicer')
log.setLevel(logging.DEBUG)


class ForwardSlicerError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class ForwardSlicer:
    """
        Forward Slicer: staring from some input, follow code paths that are
        affected by such input
    """
    MAX_ITER = 5000
    MAX_ITERS_BLOCK = 30

    def __init__(self, project, max_iter=None):
        self.project = project
        if max_iter:
            self.MAX_ITER = max_iter
        self.iters_per_block = {}
        self.affected_blocks = set()
        # tainted variable in each block
        self._tainted = {}
        self._input_data = None
        self._input = None

    @property
    def input_blocks(self):
        if self._input_data:
            return [input_block for input_block, _ in self._input_data]
        else:
            return []

    def tainted_in_block(self, block):
        return self._tainted[block][self.project.blocks_to_methods[block]]

    def tainted_in_method(self, method):
        return set.union(*[self._tainted[b][method] for b in method.blocks if b in self._tainted])

    def _merge_tainted(self, curr_block, next_block):
        curr_tainted = self._tainted[curr_block]

        if next_block in self._tainted:
            # time to merge
            next_tainted = self._tainted[next_block]

            new_tainted = dict([(m, s) for (m, s) in next_tainted.items() if m not in curr_tainted])
            new_tainted.update(dict([(m, s) for (m, s) in curr_tainted.items() if m not in next_tainted]))
            new_tainted.update(dict([(m, s.union(curr_tainted[m])) for (m, s) in next_tainted.items() if m in curr_tainted]))
            return new_tainted

        return curr_tainted

    def slice(self, input):
        self._input = input
        self._input_data = self.locate_input()

        for input_block, var in self._input_data:
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
                    # log.debug('Visiting block already visited')

                    iters_curr_block = self.iters_per_block[curr_block]
                    if iters_curr_block >= self.MAX_ITERS_BLOCK:
                        # skip it
                        # log.debug('Skipping block: visited too many times')
                        continue
                else:
                    visited.add(curr_block)

                # get variable to follow for this block
                curr_tainted = self._tainted[curr_block].get(curr_method, [])

                # better work at the statement granularity?
                for i in range(len(curr_block.statements)):
                    # get statements that use the tainted vars

                    assign_stmts, call_stmts = self.get_use_stmts(curr_block,
                                                                  curr_tainted)
                    aux = self.get_conditional_stmts(curr_block, curr_tainted)
                    cond_stmts, target_blocks = aux

                    # add blocks affected by the condition statements
                    for t_block in target_blocks:
                        self.affected_blocks.add(t_block)

                    # TODO taint object fields
                    if assign_stmts or call_stmts or cond_stmts:
                        self.affected_blocks.add(curr_block)
                        new_set = self.get_set(curr_block, assign_stmts)
                        for set_var, var_method in new_set:
                            self._tainted[curr_block][var_method].add(set_var)

                        new_calls_set = self.get_calls_set(call_stmts, curr_block)
                        for set_var, var_method in new_calls_set:
                            if var_method not in self._tainted[curr_block]:
                                self._tainted[curr_block][var_method] = set()
                            self._tainted[curr_block][var_method].add(set_var)

                        new_fields_set = self.get_fields_set(assign_stmts)
                        for field, field_method in new_fields_set:
                            if field_method not in self._tainted[curr_block]:
                                self._tainted[curr_block][field_method] = set()
                            self._tainted[curr_block][field_method].add(field)

                for next_block in self.project.cfgfull().get_next_blocks(curr_block):
                    queue.put(next_block)
                    self._tainted[next_block] = self._merge_tainted(curr_block, next_block)

    def locate_input(self):
        res = []

        if self._input['type'] == 'method':
            in_cls_name = self._input['class_name']
            in_m_name = self._input['method_name']

            for block in walk_all_blocks(self.project.classes):
                for stmt in block.statements:
                    if is_assign(stmt) and is_invoke(stmt.right_op):
                        cls_name = stmt.right_op.class_name
                        m_name = stmt.right_op.method_name
                        # TODO do we need to check params?
                        # m_params = stmt.right_op.method_params

                        if cls_name == in_cls_name and m_name == in_m_name:
                            res.append((block, stmt.left_op.name))

        elif self._input['type'] == 'method_var':
            in_cls_name = self._input['class_name']
            in_m_name = self._input['method_name']
            in_m_params = self._input['method_params']
            in_var_name = self._input['var_name']

            try:
                method = self.project.methods[(in_cls_name, in_m_name, in_m_params)]
            except KeyError:
                log.warning('Input method not found')
                return []

            for block in method.blocks:
                for stmt in block.statements:
                    if is_assign(stmt) or is_identity(stmt):
                        if hasattr(stmt.left_op, 'name') and stmt.left_op.name == in_var_name:
                            res.append((block, stmt.left_op.name))

        # else:
        #     if self._input['class_name'] not in self.project.classes:
        #         return []

        #     cls = self.project.classes[self._input['class_name']]

        #     for m in cls.methods:
        #         if m.name == self._input['method_name']:
        #             if m.params == self._input['method_params']:
        #                 for block in m.blocks:
        #                     if self.get_set_var_stmts(block.statements,
        #                                               self._input['name']):
        #                         res.append((block, self._input['name']))

        return res

    def get_use_stmts(self, block, vars):
        """
            Given a block and a list of "variable" names,
            returns the list of statements that use that variables
            and the list of invoke statements that pass that variables
        """
        assigns = []
        calls = []

        for var in vars:
            for stmt in block.statements:
                # handle the different use scenarios

                if is_assign(stmt) and is_invoke(stmt.right_op):
                    invoke_expr = stmt.right_op
                    if hasattr(invoke_expr, 'base'):
                        # --- use object method
                        # --- e.g., new = var.method()
                        # taint method
                        # TODO should we taint the "this"?
                        if stmt.right_op.base.name == var:
                            assigns.append(stmt)
                            calls.append((stmt, 0))

                    # --- param in method
                    # --- e.g., new = method(var)
                    for index, arg in enumerate(invoke_expr.args):
                        if hasattr(arg, 'name'):
                            if arg.name == var:
                                assigns.append(stmt)
                                calls.append((stmt, index))

                elif is_assign(stmt):
                    right_op = stmt.right_op
                    if is_binop_expr(right_op):
                        # --- binary operation
                        # --- e.g., new = var + other
                        if hasattr(right_op.value1, 'name'):
                            if right_op.value1.name == var:
                                assigns.append(stmt)
                        if hasattr(right_op.value2, 'name'):
                            if right_op.value2.name == var:
                                assigns.append(stmt)

                    elif is_cast_expr(right_op):
                        # --- casting
                        # --- e.g., new = (Object) var
                        if hasattr(right_op.value, 'name'):
                            if right_op.value.name == var:
                                assigns.append(stmt)

                    elif is_local_var(right_op):
                        # --- simply assignment
                        # --- e.g., new = var
                        if right_op.name == var:
                            assigns.append(stmt)

                    elif is_instance_field_ref(right_op):
                        # --- assignment from obj field
                        # --- e.g., new = obj.var
                        if right_op.field[0] == var:
                            assigns.append(stmt)
                        if right_op.base.name == var:
                            assigns.append(stmt)

                    # should we check the control flow?
                    elif is_phi_expr(right_op):
                        # --- assignment from Phi expression
                        # --- e.g., new = Phi(x, var, y)
                        for value in right_op.values:
                            if hasattr(value, 'name'):
                                if value.name == var:
                                    assigns.append(stmt)

                    elif is_array_ref(right_op):
                        # --- assignment from array
                        # --- e.g., new = var[1]
                        if right_op.base.name == var:
                            assigns.append(stmt)
                        if hasattr(right_op.index, 'name'):
                            if right_op.index.name == var:
                                assigns.append(stmt)

                    elif is_len_expr(right_op):
                        # --- assignment from array
                        # --- e.g., new = len(var)
                        if hasattr(right_op.value, 'name'):
                            if right_op.value.name == var:
                                assigns.append(stmt)

                elif is_invoke(stmt):
                    taint = False
                    # --- param in method, no assignment
                    # --- e.g., method(var)
                    invoke_expr = stmt.invoke_expr
                    for index, arg in enumerate(invoke_expr.args):
                        if hasattr(arg, 'name'):
                            if arg.name == var:
                                calls.append((stmt, index))
                                taint = True

                    # --- e.g., obj.method(var)
                    #           taint obj
                    if taint and hasattr(invoke_expr, 'base'):
                        if hasattr(invoke_expr.base, 'name'):
                            assigns.append(stmt)

                    # --- e.g., var.method(param)
                    #           taint param
                    if hasattr(invoke_expr, 'base'):
                        if invoke_expr.base.name == var:
                            assigns.append(stmt)

                elif is_condition(stmt):
                    # TODO basic condition
                    if hasattr(stmt.condition.value1, 'name'):
                        if stmt.condition.value1.name == var:
                            assigns.append(stmt)
                    if hasattr(stmt.condition.value2, 'name'):
                        if stmt.condition.value2.name == var:
                                assigns.append(stmt)

        return assigns, calls

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
            if is_assign(stmt) or is_identity(stmt):
                ass_to = stmt.left_op.name if hasattr(stmt.left_op, 'name') \
                    else stmt.left_op.base.name
                if ass_to == var:
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
                else:
                    invoke_expr = stmt.right_op

                # we taint the obj even if the method returns
                # is this OK?
                # --- x = obj.method(var)
                if hasattr(invoke_expr, 'base'):
                    if hasattr(invoke_expr.base, 'name'):
                        var_sets.add((invoke_expr.base.name, method))

                for arg in invoke_expr.args:
                    if hasattr(arg, 'name'):
                        var_sets.add((arg.name, method))

            if is_condition(stmt):
                # TODO basic condition
                if hasattr(stmt.condition.value1, 'name'):
                    var_sets.add((stmt.condition.value1.name, method))
                elif hasattr(stmt.condition.value2, 'name'):
                    var_sets.add((stmt.condition.value2.name, method))

        return var_sets

    def get_calls_set(self, stmts, block):
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
            container_m = self.project.blocks_to_methods[block]

            targets = self.project.hierarchy().resolve_invoke(invoke_expr, method, container_m)

            for target in targets:
                var_name = None
                # Assumption: Params are defined in the first block
                try:
                    for stmt in target.blocks[0].statements:
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
                    res.add((var_name, target))

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
