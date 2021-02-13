Turi
====

Turi is built on top of `pysoot`.

## Install

To install turi as a package, together with its dependencies, run: 
```
./setup.sh -e <VENV_NAME>
```
Developer option:
```
./setup.sh -e <VENV_NAME> -w develop
```

### Dependencies: manual installation

* Install python `networkx`:
    ```
    pip install networkx
    ```

* Install `pysoot`:
    ```
    pip install -e git+https://github.com/conand/pysoot#egg=pysoot
    ```

## Run

```python
from turi import Project

p = Project(<PATH_TO_APP>)

cfg = p.cfgfull()

callgraph = p.callgraph()
```
