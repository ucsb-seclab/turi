import nose

from turi.project import Project
from turi.utils import get_method_key


def test_example_1():
    p = Project('tests/build/BackwardSlicerExample1.jar')

    affected_methods = set()

    inp = {'type': 'method_var',
           'class_name': 'BackwardSlicerExample1',
           'method_name': 'dosomething',
           'method_params': ['java.lang.String'],
           'var_name': 'r1'}

    # Backward slicing
    slicer = p.backwardslicer()
    slicer.slice(inp)

    # Get affected methods
    for b in slicer.affected_blocks:
        affected_methods.add(get_method_key(p.blocks_to_methods[b]))

    correct = [('BackwardSlicerExample1', 'dosomething', ('java.lang.String',)),
               ('BackwardSlicerExample1', 'func', ('java.lang.String',)),
               ('MyClass', 'append', ('java.lang.String', 'java.lang.String')),
               ('BackwardSlicerExample1', 'main', ('java.lang.String[]',))]

    # test correct results
    for c in correct:
        nose.tools.assert_in(c, affected_methods)


def main():
    test_example_1()


if __name__ == '__main__':
    main()

