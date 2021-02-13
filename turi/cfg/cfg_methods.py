import networkx
import logging

from ..cfg import CFGBase
from ..statements import is_condition, is_switch, is_jump

logging.basicConfig()
log = logging.getLogger("CFGMethods")
log.setLevel(logging.DEBUG)


class CFGMethod(CFGBase):
    """
        CFG for one method
    """

    def __init__(self, method):
        self.name = method.name
        self.class_name = method.class_name
        self.params = method.params
        self.method = method
        self.graph = networkx.DiGraph()

        self.build()

    def build(self):
        # new pysoot already has intra-method CFG
        link_previous_block = False
        previous_block = None

        for block in self.method.blocks:
            self.graph.add_node(block)

            if link_previous_block:
                self.graph.add_edge(previous_block, block)

            link_previous_block = False
            previous_block = None

            for stmt in block.statements:
                if is_condition(stmt):
                    self._add_jump(self.method, block, stmt)
                    link_previous_block = True
                    previous_block = block
                if is_switch(stmt):
                    self._add_switch(self.method, block, stmt)
                if is_jump(stmt):
                    self._add_jump(self.method, block, stmt)
                if self._is_unknown(stmt):
                    log.warning('Unknown Statement:{}'.format(str(type(stmt))))

            if self._link_to_next(block):
                link_previous_block = True
                previous_block = block

            for excep_pred in self.method.exceptional_preds[block]:
                self.graph.add_node(excep_pred)
                self.graph.add_edge(excep_pred, block)


def get_method_CFGs(classes):
    """
        One CFG for each method
    """
    CFGs = []

    for cls_name, cls in classes.items():
        for method in cls.methods:
            CFGs.append(CFGMethod(method))

    return CFGs
