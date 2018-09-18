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
        include_dirs=['phorth/include'],
        language='c++',
        extra_compile_args=[
            '-Wall',
            '-Wextra',
            '-Wno-write-strings',
            '-Wno-cast-function-type',
            '-Wno-missing-field-initializers',
            '-std=gnu++17',
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
    package_data={
        'phorth': ['LICENSE'],
    },
    long_description=long_description,
    license='GPL-2+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: C++',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python',
        'Topic :: Software Development :: Compilers',
        'Topic :: Software Development :: Interpreters',
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
