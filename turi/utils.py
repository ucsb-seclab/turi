"""
    Utils functions
"""


def get_method_key(method):
    return (method.class_name, method.name, method.params)


def same_method_signature(method1, method2):
    return method1.name == method2.name and method1.params == method2.params


def walk_all_statements(classes, methods=None):
    for class_name, cls in classes.items():
        for method in cls.methods:
            if methods is not None and method not in methods:
                continue

            for block in method.blocks:
                for stmt in block.statements:
                    yield cls, method, stmt


def walk_all_blocks(classes, methods=None):
    for class_name, cls in classes.items():
        for method in cls.methods:
            if methods is not None and method not in methods:
                continue
            for block in method.blocks:
                yield block
