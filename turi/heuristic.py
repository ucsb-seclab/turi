import logging
from collections import namedtuple
from .statements import is_invoke, is_instance_field_ref, is_assign, is_static_field_ref
from .utils import get_method_key
from .stub import call_stub

logging.basicConfig()
log = logging.getLogger("Heuristic")
log.setLevel(logging.DEBUG)

Target = namedtuple("Target", ["type_op", "class_name", "method_name", "method_params", "var_name"])

class Heuristic:
    """
        Heuristic class
    """
    def __init__(self, project):
        self._project = project
        self._classes = project.classes

        # reflection
        self._targets = set()
        self._collection_types = {'java.util.LinkedList', 'java.util.List'}
        self._stubbed_methods = {('com.ainfosec.Util', 'getClassesForPackage')}
        self._result = set()
        self.results = dict()

    def _get_class_method(self, stmt):
        if hasattr(stmt, 'invoke_expr'):
            fld = 'invoke_expr'
        else:
            fld = 'right_op'

        called_cls_name = getattr(stmt, fld).class_name
        called_method_name = getattr(stmt, fld).method_name

        return (called_cls_name, called_method_name)

    def _is_reflection_class(self, stmt):
        (cl, me) = self._get_class_method(stmt)
        if ((cl == "java.lang.Object") and (me == "getClass")):
            return True
        return False

    def _is_stubbed(self, class_name, method_name):
        if (class_name, method_name) in self._stubbed_methods:
            return True
        return False

    def _is_defined(self, class_name, method_name):
        defined = False
        if class_name in self._classes:
            cls = self._classes[class_name]
            for mm in cls.methods:
                if method_name in mm.name:
                    defined = True
                    break
        return defined

    def _who_gets_field(self, fld_name, cls, method, stmt):
        if is_assign(stmt):
            left_op =  getattr(stmt, 'left_op')
            right_op = getattr(stmt, 'right_op')

            if is_instance_field_ref(right_op):
                if hasattr(right_op, 'field'):
                    if fld_name in right_op.field[0]:
                        if 'SootLocal' in str(type(left_op)):
                            return Target('method_var', cls.name, method.name, method.params, stmt.left_op.name)

    def _who_stores_to_field(self, fld_name, cls, method, stmt):
        res = None
        if is_assign(stmt):
            left_op =  getattr(stmt, 'left_op')

            # static
            if is_static_field_ref(left_op):
                if hasattr(left_op, 'field'):
                    if fld_name in left_op.field[0]:
                        if 'SootLocal' in str(type(stmt.right_op)):

                            slicer = self._slice(Target('method_var', cls.name, method.name, method.params, stmt.right_op.name))
                            for sl_block in slicer.affected_blocks:
                                for sl_stmt in sl_block.statements:
                                    if hasattr(sl_stmt, 'right_op'):
                                        op = sl_stmt.right_op
                                        if is_invoke(op):
                                            if hasattr(op, 'method_name'):
                                                sl_md_name = op.method_name
                                                sl_cls_name = op.class_name

                                                #we need stub
                                                if not (self._is_defined(sl_cls_name, sl_md_name)) or self._is_stubbed(sl_cls_name, sl_md_name):
                                                    res = call_stub(sl_md_name, self._classes, op.args)
        return res

    #find who stores in the field
    def _store_to_fld(self, resolvent):
        resolvents = set()
        cls = self._classes[resolvent[0]]
        fld_name = resolvent[1]
        if fld_name in cls.fields:
            fld = cls.fields[fld_name]
        else:
            return resolvents
        for method in cls.methods:
            for block in method.blocks:
                for stmt in block.statements:
                    res = self._who_stores_to_field(fld_name, cls, method, stmt)
                    if not res == None:
                        resolvents = resolvents | res
        return resolvents

    def _find_reflection_targets(self):
        for cls_name, cls in self._classes.items():
            for method in cls.methods:
                for block in method.blocks:
                    for stmt in block.statements:
                        if is_invoke(stmt):
                            if (self._is_reflection_class(stmt)):
                                ref_reg = getattr(stmt, 'right_op').base
                                self._targets.add(Target('method_var', cls.name, method.name, method.params, stmt.right_op.base.name))

    def _find_store_to_list(self, resolvent):
        resolvents = set()
        getters = set()
        cls = self._classes[resolvent[0]]
        fld_name = resolvent[1]
        if fld_name in cls.fields:
            fld = cls.fields[fld_name]
        else:
            return resolvents
        for method in cls.methods:
            for block in method.blocks:
                for stmt in block.statements:
                    gets = self._who_gets_field(fld_name, cls, method, stmt)
                    if not gets == None:
                        getters.add(gets)
                    #we are looking for addtion to list call, we are insterested in Arguments
                    if hasattr(stmt, 'right_op'):
                        if is_invoke(stmt.right_op):
                            if 'java.util.LinkedList' in stmt.right_op.class_name:
                                if 'add' in stmt.right_op.method_name:
                                    for getter in getters:
                                        if getter.var_name in stmt.right_op.base.name:
                                            #argument reveals what we store to the collection
                                            for arg in stmt.right_op.args:
                                                resolvents.add(Target('method_var', cls.name, method.name, method.params, arg.name))
        return resolvents

    def _slice(self, target):
        inp = {'type': target.type_op,
                'class_name': target.class_name,
                'method_name': target.method_name,
                'method_params': target.method_params,
                'var_name': target.var_name}
        slicer = self._project.backwardslicer()
        slicer.slice(inp)
        return slicer

    def _analyze_reflection_targets(self, target):
        affected_methods = set()

        # Backward slicing
        slicer = self._slice(target)

        # Get affected methods
        for b in slicer.affected_blocks:
            affected_methods.add(get_method_key(self._project.blocks_to_methods[b]))

        '''
        simple heuristic:
        try to find class name in the backward slice,
          if class name is there -> check whether the fields of this class are also there
            if the fields are there -> they become candidates for the Reflection resolvents (ideally it is one field)
            if there are no fields of the class in the backwar slice -> class itself should be a candidate
          if no class is in the backward slice -> fail

        '''

        resolvents = set()

        for block in slicer.affected_blocks:
            tainted = slicer.tainted_in_block(block)

            for taint in tainted:
                # static field
                if 'tuple' in str(type(taint)):
                    cls = self._classes[taint[1]]
                    fld = cls.fields[taint[0]]
                    resolvents.add((cls.name, taint[0], fld[1]))
                else:
                    try:
                        _field = False
                        cls = self._classes[taint]
                        for taint in tainted:
                            try:
                                fld = cls.fields[taint]
                                resolvents.add((cls.name, taint, fld[1]))
                                _field = True
                                break
                                # there is no field in tainted, so it's a class
                                if not _field:
                                    resolvents.add(cls)
                            except KeyError as e:
                                # there is no field, just go on
                                pass
                    except KeyError as e:
                    # there is no class here, just go on
                        pass
        res = set()
        for resolvent in resolvents:
            #if we find classes here -> we are done!
            if resolvent in self._classes:
                res.add(self._classes[resolvent])
            #deal with fields, they are tuples
            if 'tuple' in str(type(resolvent)):
                field_type = resolvent[2]
                if field_type in self._collection_types:
                    #oh no, we need to know what is stored in a collection type!
                    list_stores = self._find_store_to_list(resolvent)

                    for list_store in list_stores:
                        clss = self._analyze_reflection_targets(list_store)
                        if not clss == None:
                            self._result = self._result | clss

                    res = res | self._store_to_fld(resolvent)
        return res

    def resolve_reflection_targets(self):
        # first we find the places where the classes/fields are accessed and memorise them
        self._find_reflection_targets()
        # now the real deal
        for target in self._targets:
            self._result = set()
            self._analyze_reflection_targets(target)
            self.results[target] = self._result
