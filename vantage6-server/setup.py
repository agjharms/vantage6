"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


# Read the API version from disk 
with open(path.join(here, 'joey', 'VERSION')) as fp:
    __version__ = fp.read()


# Setup the package
setup(
    name='joey',
    version=__version__,
    description='Package and utilities for distributed learning',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/IKNL/joey',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    python_requires='>=3',
    install_requires=[
        'appdirs',
        'bcrypt',
        'click',
        'docker',
        'eventlet',
        'flask',
        'flask-cors',
        'flask-jwt-extended',
        'flask-restful',
        'flask-sqlalchemy',
        'flask-marshmallow',
        'flask-socketio',
        'socketIO_client',
        'marshmallow',
        'marshmallow-sqlalchemy',
        'pyyaml',
        'psutil',
        'psycopg2',
        'requests',
        'termcolor',
        'sqlalchemy',
        'iknl-flasgger',
        'schema',
        'questionary',
        'ipython',
        'cryptography'
    ],
    package_data={  
        'joey': [
            'server/server.wsgi', 
            'VERSION', 
            '_data/**/*.yaml',
            '_data/*.yaml',
            'server/resource/swagger/*.yaml'
        ],
    },
    entry_points={
        'console_scripts': [
            'jnode=joey.node_manager.cli.node_manager:cli_node',
            'jserver=joey.server.cli.server:cli_server',
            'jdev=joey.util.cli.develop:cli_develop'
        ],
    }
)
