import logging
import networkx

from ..statements import is_condition, is_switch, is_jump, is_invoke, is_ret

logging.basicConfig()
log = logging.getLogger("CFGBase")
log.setLevel(logging.WARN)


# [DONE] return from call add edge
# [DONE] goto no if
# [DONE] 8
# [DONE] class hierarchy
# [DONE] per method CFG + "zoom in snapshot"
# [DONE] calls to init?
# [DONE]"keep going" edge
# [DONE] pysoot statements
# ThrowStmt
# InnerClass Thread trick

class CFGBase:
    """
        The base class for CFG
    """

    def __init__(self):
        self.graph = None
        self.classes = []
        self.method = None

    def get_next_blocks(self, block):
        return self.graph.successors(block)

    def get_prev_blocks(self, block):
        return self.graph.predecessors(block)

    def get_paths(self, source, sink):
        return networkx.all_simple_paths(self.graph, source, sink)

    def _add_method(self, method):
        link_previous_block = False
        previous_block = None

        for block in method.blocks:
            self.graph.add_node(block)

            if link_previous_block:
                self.graph.add_edge(previous_block, block)

            link_previous_block = False
            previous_block = None

            for stmt in block.statements:
                if is_invoke(stmt):
                    self._add_invoke(method, block, stmt)
                if is_condition(stmt):
                    self._add_jump(method, block, stmt)
                    link_previous_block = True
                    previous_block = block
                if is_switch(stmt):
                    self._add_switch(method, block, stmt)
                if is_jump(stmt):
                    self._add_jump(method, block, stmt)
                if self._is_unknown(stmt):
                    log.debug('Unknown Statement: ' + str(type(stmt)))

            if self._link_to_next(block):
                link_previous_block = True
                previous_block = block

            for excep_pred in method.exceptional_preds[block]:
                self.graph.add_node(excep_pred)
                self.graph.add_edge(excep_pred, block)

    def _add_jump(self, method, block, stmt):
        target_block_label = stmt.target
        target_block = method.block_by_label[target_block_label]

        self.graph.add_node(target_block)
        self.graph.add_edge(block, target_block)

    def _add_switch(self, method, block, stmt):
        # Switch default target
        target_block_label = stmt.default_target
        target_block = method.block_by_label[target_block_label]

        self.graph.add_node(target_block)
        self.graph.add_edge(block, target_block)

        # Switch targets
        for target_block_label in stmt.lookup_values_and_targets.values():
            target_block = method.block_by_label[target_block_label]

            self.graph.add_node(target_block)
            self.graph.add_edge(block, target_block)

    def _link_to_next(self, block):
        '''
            Link to next block if last statement is not a goto, ret, exit
        '''
        last_stmt = block.statements[-1]
        if is_jump(last_stmt):
            return False

        if is_ret(last_stmt):
            return False

        if is_invoke(last_stmt):
            if hasattr(last_stmt, 'invoke_expr'):
                fld = 'invoke_expr'
            else:
                fld = 'right_op'

            called_cls_name = getattr(last_stmt, fld).class_name
            called_method_name = getattr(last_stmt, fld).method_name

            if 'java.lang.System' in called_cls_name:
                if 'exit' in called_method_name:
                    return False

        return True

    def _is_unknown(self, stmt):
        if 'ExitMonitorStmt' in str(type(stmt)):
            return True

        if 'EnterMonitorStmt' in str(type(stmt)):
            return True

        if 'BreakpointStmt' in str(type(stmt)):
            return True

        if 'ThrowStmt' in str(type(stmt)):
            return True

        else:
            return False
