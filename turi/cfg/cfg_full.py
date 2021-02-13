import networkx
import logging

from ..cfg import CFGBase
from ..statements import is_ret
from ..hierarchy import NoConcreteDispatch

logging.basicConfig()
log = logging.getLogger("CFGFull")
log.setLevel(logging.DEBUG)


class CFGFull(CFGBase):
    """
        Build CFG on top of pysoot
        Full CFG ~> link (and link back) calls and returns
    """

    def __init__(self, project, ret_edges=False):
        self.project = project
        self.graph = networkx.DiGraph()
        self.ret_edges = ret_edges

        self.build()

    def build(self):
        for cls_name, cls in self.project.classes.items():
            for method in cls.methods:
                self._add_method(method)

    def _add_invoke(self, container_m, block, invoke):
        if hasattr(invoke, 'invoke_expr'):
            invoke_expr = invoke.invoke_expr

        else:
            invoke_expr = invoke.right_op

        cls_name = invoke_expr.class_name
        method_name = invoke_expr.method_name
        method_params = invoke_expr.method_params

        if cls_name not in self.project.classes:
            # external classes are not supported
            return

        try:
            method = self.project.methods[(cls_name, method_name, method_params)]
        except KeyError as e:
            # TODO should we add a dummy node for "external" methods?
            log.warning("Cannot handle call to external method")
            return

        try:
            targets = self.project.hierarchy().resolve_invoke(invoke_expr, method, container_m)
        except NoConcreteDispatch as e:
            targets = []
            log.warning('Could not resolve concrete dispatch. External method?')

        for target in targets:
            if 'NATIVE' in target.attrs or 'ABSTRACT' in target.attrs:
                # TODO should we use a dummy node for native methods?
                continue

            if target.class_name in self.project.classes:
                self.graph.add_node(target.blocks[0])
                self.graph.add_edge(block, target.blocks[0])

                if self.ret_edges:
                    # add an edge for returning after call
                    ret_blocks = self._get_method_ret_blocks(target)
                    for ret_block in ret_blocks:
                        self.graph.add_node(ret_block)
                        self.graph.add_edge(ret_block, block)

    def _get_method_ret_blocks(self, method):
        ret_blocks = set()

        for block in method.blocks:
            for stmt in block.statements:
                # Return statement
                if is_ret(stmt):
                    ret_blocks.add(block)
                    break

        return ret_blocks
