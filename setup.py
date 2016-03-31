#!/usr/bin/env python
from setuptools import setup, Extension
import sys

long_description = ''

if 'upload' in sys.argv:
    with open('README.rst') as f:
        long_description = f.read()


def extension(name):
    return Extension(
        'phorth.' + name,
        ['phorth/{name}.cc'.format(name=name)],
        libraries=['py'],
        library_dirs=['../../c++/libpy'],
        include_dirs=['../../c++/libpy/include', 'phorth/include'],
        language='C++',
        extra_compile_args=[
            '-Wall',
            '-Wextra',
            '-Wno-unused-parameter',
            '-Wno-missing-field-initializers',
            '-Wno-write-strings',
            '-std=gnu++14',
            '-O0',
        ],
    )

setup(
    name='phorth',
    version='0.1.0',
    description='A forth-like programming language that runs on the'
    ' CPython VM',
    author='Joe Jevnik',
    author_email='joejev@gmail.com',
    packages=[
        'phorth',
    ],
    long_description=long_description,
    license='GPL-2',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: POSIX',
    ],
    url='https://github.com/llllllllll/phorth',
    ext_modules=[
        extension('_primitives'),
        extension('_runner'),
    ],
    install_requires=[
        'codetransformer>=0.4.4',
    ],
)
