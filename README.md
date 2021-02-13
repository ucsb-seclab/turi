Turi
====

Turi is a simple Java/Android static analysis framework.

## Install

```
mkvirtualenv --python=`which python3` turi
pip install -e git+https://github.com/angr/pysoot#egg=pysoot
python setup.py install
```

## Run

```python
from turi import Project

p = Project(<PATH_TO_APP>)

cfg = p.cfgfull()

callgraph = p.callgraph()
```
