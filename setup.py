#!/usr/bin/env python

import sys
from os.path import join

from setuptools import setup

sys.path.append('.')

scripts = [join('bin', filename) for filename in ['apns']]

modname = 'apns'

setup(
    name='apns',
    version="1.0.4",
    python_requires=">=3.6",
    description='AP Network Simulation emulator with Container support',
    author='Aleksandr Loshkarev',
    author_email='hi@aloshkarev.ru',
    packages=['apns', 'apns.library', 'apns.examples'],
    package_data={
        'apns': ['data/signal_table_ieee80211ax',
                       'data/signal_table_ieee80211n_gi20',
                       'data/signal_table_ieee80211n_gi40',
                       'data/signal_table_ieee80211n_sgi20',
                       'data/signal_table_ieee80211n_sgi40',
                       'mnexec/CMakeLists.txt',
                       'mnexec/mnexec.c'
                       ]
    },
    include_package_data=True,
    long_description="""
        AP Network Simulation is a network emulator which uses lightweight
        virtualization to create virtual networks for rapid
        prototyping of Software-Defined Wireless Network (SDWN) designs
        using OpenFlow.
        """,
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: System :: Emulators",
    ],
    keywords='networking emulator protocol Internet OpenFlow SDN',
    license='BSD',
    install_requires=[
        'six',
        'setuptools',
        'matplotlib',
        'urllib3',
        'docker',
        'pytest',
        'more-itertools',
        'requests',
        'pexpect',
        "numpy",
        'ansible ~= 7.5',
        'python-iptables'
    ],
    scripts=scripts,
)
