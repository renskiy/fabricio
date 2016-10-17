import sys

from distutils.core import setup
from setuptools import find_packages

with open('README.rst') as description:
    long_description = description.read()

install_requires = [
    'Fabric>=1.1,<2.0',
    'frozendict>=1.2,<2.0',
    'cached-property>=1.3',
    'docker-py>=1.8.1,<2.0',
    'six>=1.4.0',
]

if sys.version_info < (2,7):
    install_requires.append(
        'ordereddict>=1.1',
    )

setup(
    name='fabricio',
    version='0.3.6',
    author='Rinat Khabibiev',
    author_email='srenskiy@gmail.com',
    packages=list(map('fabricio.'.__add__, find_packages('fabricio'))) + ['fabricio'],
    url='https://github.com/renskiy/fabricio',
    license='MIT',
    description='fabricio',
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: Utilities',
        'Topic :: System :: Networking',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
    ],
    install_requires=install_requires,
)
