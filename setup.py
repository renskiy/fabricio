from distutils.core import setup
from setuptools import find_packages

with open('README.rst') as description:
    long_description = description.read()

setup(
    name='fabricio',
    version='0.2.8',
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
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'Fabric>=1.1,<2.0',
        'cached-property>=1.3',
        'docker-py>=1.8.1',
        'six>=1.4.0',
    ],
)
