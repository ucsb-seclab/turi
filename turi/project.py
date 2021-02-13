import os
import pickle
import logging
from pysoot.lifter import Lifter

from .cfg import CFGFull, get_method_CFGs
from .hierarchy import Hierarchy
from .backward_slicer import BackwardSlicer
from .forward_slicer import ForwardSlicer
from .callgraph import CallGraph
from .utils import get_method_key
from .common import x_ref


logging.basicConfig()
log = logging.getLogger("turi-project")
log.setLevel(logging.DEBUG)


class Project:
    """
        Project
        Contains global data
    """
    def __init__(self, app_path, input_format=None, android_sdk=None, lifter=None, pickled=None):
        self.app_path = app_path
        self.input_format = input_format
        self.android_sdk = android_sdk
        self.pickle = pickle
        self.pickled = pickled

        # initialize empty data structure
        self._lifter = lifter
        self._methods = {}
        self._blocks_to_methods = {}
        self._stmts_to_blocks = {}
        self._stmts_to_classes = {}
        self._hierarchy = None
        self._cfg_full = None
        self._cfg_full_ret_edges = None
        self._cfg_methods = None
        self._callgraph = None

        self.setup()

    @property
    def lifter(self):
        return self._lifter

    @property
    def classes(self):
        return self._classes

    @property
    def methods(self):
        return self._methods

    @property
    def blocks_to_methods(self):
        return self._blocks_to_methods

    @property
    def stmts_to_blocks(self):
        return self._stmts_to_blocks

    @property
    def stmts_to_classes(self):
        return self._stmts_to_classes

    def setup(self):
        should_pickle = False
        should_unpickle = False
        if self.pickled is not None:
            pickled_path = os.path.abspath(self.pickled)
            if os.path.exists(pickled_path):
                should_unpickle = True
            else:
                should_pickle = True

        if should_unpickle:
            with open(pickled_path, 'rb') as fp:
                self._classes = pickle.load(fp)
        else:
            if not self._lifter:
                log.info('Lifting app')
                if self.android_sdk is not None and self.input_format is not None:
                    self._lifter = Lifter(self.app_path,
                                          input_format=self.input_format,
                                          android_sdk=self.android_sdk)
                else:
                    self._lifter = Lifter(self.app_path)

            self._classes = self._lifter.classes
            

            if should_pickle:
                with open(pickled_path, 'wb') as fp:
                    pickle.dump(self._classes, fp, protocol=2)

        for _, cls in self._classes.items():
            for method in cls.methods:
                method_key = get_method_key(method)
                self._methods[method_key] = method

                for block in method.blocks:
                    self._blocks_to_methods[block] = method

                    for stmt in block.statements:
                        self._stmts_to_blocks[stmt] = block
                        self._stmts_to_classes[stmt] = cls

    def cfgfull(self, instantiate=False):
        if self._cfg_full is None or instantiate:
            log.info('Instantiating CFGFull')
            self._cfg_full = CFGFull(self)

        return self._cfg_full

    def cfgfull_retedges(self, instantiate=False):
        if self._cfg_full_ret_edges is None or instantiate:
            log.info('Instantiating CFGFull (with return edges)')
            self._cfg_full_ret_edges = CFGFull(self, ret_edges=True)

        return self._cfg_full_ret_edges

    def cfgmethods(self, instantiate=False):
        if self._cfg_methods is None or instantiate:
            log.info('Instantiating CFG Methods')
            self._cfg_methods = get_method_CFGs(self.classes)

        return self._cfg_methods

    def hierarchy(self, instantiate=False):
        if self._hierarchy is None or instantiate:
            log.info('Instantiating Hierarchy')
            self._hierarchy = Hierarchy(self)

        return self._hierarchy

    def backwardslicer(self):
        return BackwardSlicer(self)

    def forwardslicer(self):
        return ForwardSlicer(self)

    def callgraph(self, instantiate=False):
        if self._callgraph is None or instantiate:
            log.info('Instantiating CallGraph')
            self._callgraph = CallGraph(self)

        return self._callgraph

    def x_ref(self, thing, thing_type):
        return x_ref(thing, thing_type, self)
