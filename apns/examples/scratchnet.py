#!/usr/bin/python

"""
Build a simple network from scratch, using apns primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.

For most tasks, the higher-level API will be preferable.
"""

from time import sleep

from apns.link import Link
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Node
from apns.util import quietRun


def scratchNet(cname='controller', cargs='-v ptcp:'):
    "Create network from scratch using Open vSwitch."

    info("--- Create Network Elements\n")
    controller = Node('c0', inNamespace=False)
    switch = Node('s0', inNamespace=False)
    h0 = Node('h0')
    h1 = Node('h1')

    info("--- Links\n")
    Link(h0, switch)
    Link(h1, switch)

    info("--- Configuring hosts\n")
    h0.setIP('192.168.123.1/24')
    h1.setIP('192.168.123.2/24')
    info(str(h0) + '\n')
    info(str(h1) + '\n')

    info("--- Start using Open vSwitch\n")
    controller.cmd(cname + ' ' + cargs + '&')
    switch.cmd('ovs-vsctl del-br dp0')
    switch.cmd('ovs-vsctl add-br dp0')
    for intf in list(switch.intfs.values()):
        print((switch.cmd('ovs-vsctl add-port dp0 %s' % intf)))

    # Note: controller and switch are in root namespace, and we
    # can connect via loopback interface
    switch.cmd('ovs-vsctl set-controller dp0 tcp:127.0.0.1:6633')

    info('--- Waiting for switch to connect to controller')
    while 'is_connected' not in quietRun('ovs-vsctl show'):
        sleep(1)
        info('.')
    info('\n')

    info("--- Running test\n")
    h0.cmdPrint('ping -c1 ' + h1.IP())

    info("--- Stop\n")
    controller.cmd('kill %' + cname)
    switch.cmd('ovs-vsctl del-br dp0')
    switch.deleteIntfs()
    info('\n')


if __name__ == '__main__':
    setLogLevel('info')
    info('--- Scratch network demo (kernel datapath)\n')
    Wmnet.init()
    scratchNet()
