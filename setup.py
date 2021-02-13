from setuptools import setup
from setuptools import find_packages

packages = find_packages()
print(packages)
setup(
    name='turi',
    version='1.0',
    description='Turi',
    packages=packages,
    include_package_data=True,
    install_requires=['networkx', 'nose']
)
