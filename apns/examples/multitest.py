#!/usr/bin/python

"""
This example shows how to create a network and run multiple tests.
For a more complicated test example, see udpbwtest.py.
"""

from apns.cli import CLI
from apns.log import lg, info
from apns.net import Wmnet
from apns.node import OVSKernelSwitch
from apns.topolib import TreeTopo


def ifconfigTest(net):
    "Run ifconfig on all hosts in net."
    hosts = net.hosts
    for host in hosts:
        info(host.cmd('ifconfig'))


if __name__ == '__main__':
    lg.setLogLevel('info')
    info("--- Initializing Wmnet and kernel modules\n")
    OVSKernelSwitch.setup()
    info("--- Creating network\n")
    network = Wmnet(TreeTopo(depth=2, fanout=2), switch=OVSKernelSwitch)
    info("--- Start\n")
    network.start()
    info("--- Running ping test\n")
    network.pingAll()
    info("--- Running ifconfig test\n")
    ifconfigTest(network)
    info("--- Starting CLI (type 'exit' to exit)\n")
    CLI(network)
    info("--- Stop\n")
    network.stop()
