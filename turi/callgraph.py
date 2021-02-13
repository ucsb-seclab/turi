import networkx
import logging

from collections import defaultdict

from .statements import *
from .utils import walk_all_blocks
from .hierarchy import NoConcreteDispatch

logging.basicConfig()
log = logging.getLogger('CallGraph')
log.setLevel(logging.DEBUG)


class CallGraph:
    """
        Build call graph
    """

    def __init__(self, project):
        self.project = project
        self.graph = networkx.DiGraph()
        self._call_sites = defaultdict(lambda: defaultdict(list))
        self.build()

    def build(self):
        for block in walk_all_blocks(self.project.classes):
            method = self.project.blocks_to_methods[block]
            self.graph.add_node(method)
            for stmt in block.statements:
                if is_invoke(stmt):
                    self._add_invoke(method, block, stmt)

    def _add_invoke(self, container_m, block, invoke):
        if hasattr(invoke, 'invoke_expr'):
            invoke_expr = invoke.invoke_expr

        else:
            invoke_expr = invoke.right_op

        cls_name = invoke_expr.class_name
        method_name = invoke_expr.method_name
        method_params = invoke_expr.method_params

        if cls_name not in self.project.classes:
            # external classes are currently not supported
            return

        try:
            method = self.project.methods[(cls_name, method_name, method_params)]
        except KeyError as e:
            # TODO should we add a dummy node for "external" methods?
            log.warning('Cannot handle call to external method')
            return

        try:
            targets = self.project.hierarchy().resolve_invoke(invoke_expr, method, container_m)
        except NoConcreteDispatch as e:
            targets = []
            log.warning('Could not resolve concrete dispatch. External method?')

        for target in targets:
            if target.class_name in self.project.classes:
                self.graph.add_node(target)
                self.graph.add_edge(container_m, target)
                self._call_sites[container_m][target].append(invoke_expr)

    def get_call_sites(self, method, target):
        return self._call_sites[method][target]

    def next(self, method):
        return self.graph.successors(method)

    def prev(self, method):
        return self.graph.predecessors(method)
