Turi
====

Turi analyzes Java programs to identify space complexity vulnerabilities.

It is built on top of `pysoot`.

## Install

To install turi as a package, together with its dependencies, run: 
```
./setup.sh -e <VENV_NAME>
```
You can also specify developer option to use the local folder for the package:
```
./setup.sh -e <VENV_NAME> -w develop
```
This means changes to your local sources are immediately effective.

### Dependencies: manual installation

* Install python `networkx`:
    ```
    pip install networkx
    ```

* Install `pysoot`:
    ```
    pip install -e git+https://github.com/conand/pysoot#egg=pysoot
    ```

* To run or work on the angr part, install java angr following [these instructions](./INSTALL_JAVA_ANGR.md).

## Run

To run turi's analysis:
```
python run_turi.py <PATH_TO_CONFIG_FILE>
```
You can have a look at config file samples in the `data` folder.

To use turi framework and dig into the internals. you can start from this:
```python
from turi import Project

p = Project(<PATH_TO_APP>)

cfg = p.cfgfull()

callgraph = p.callgraph()
```
