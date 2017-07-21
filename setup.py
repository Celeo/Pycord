from setuptools import setup
import re


with open('pycord/__init__.py') as f:
    version = re.search(r'(\d+\.\d+\.\d+)', f.read()).group(1)

setup(
    name='PycordLib',
    author='Matt Boulanger',
    author_email='celeodor@gmail.com',
    version=version,
    license='MIT',
    description='Simple Discord bot library',
    url='https://github.com/Celeo/Pycord',
    platforms='any',
    packages=['pycord'],
    keywords=['discord'],
    install_requires=[
        'requests>=2.18.1',
        'websocket-client>=0.44.0'
    ],
    classifiers=[
        'Environment :: Console',
        'Environment :: Web Environment',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries'
    ]
)
