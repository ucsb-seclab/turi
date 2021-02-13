import logging

logging.basicConfig()
log = logging.getLogger("Stub")
log.setLevel(logging.DEBUG)

def call_stub(method_name, classes, args):
    if method_name in 'getClassesForPackage':
        arg = args[0].value
        return getClassesForPackage(classes, arg)

def getClassesForPackage(classes, package_name):
    clss = set()
    for key, value in classes.items():
        if package_name[1:-1] in key:
            clss.add(value)
    return clss
