#!/usr/bin/env python

"""This example creates a simple network topology with 1 AP and 2 stations"""

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology():
    """Create a network."""
    net = Wmnet()

    info("--- Create Network Elements\n")
    sta_arg, ap_arg = {}, {}
    if '-v' in sys.argv:
        sta_arg = {'nvif': 2}
    else:
        # isolate_clientes: Client isolation can be used to prevent low-level
        # bridging of frames between associated stations in the BSS.
        # By default, this bridging is allowed.
        # OpenFlow rules are required to allow communication among nodes
        ap_arg = {'client_isolation': True}

    ap1 = net.addAP('ap1', ssid="simpletopo", mode="g",
                             channel="5", **ap_arg)
    sta1 = net.addSta('sta1', **sta_arg)
    sta2 = net.addSta('sta2')
    c0 = net.addController('c0')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)

    info("--- Start\n")
    net.build()
    c0.start()
    ap1.start([c0])

    if '-v' not in sys.argv:
        ap1.cmd('ovs-ofctl add-flow ap1 "priority=0,arp,in_port=1,'
                'actions=output:in_port,normal"')
        ap1.cmd('ovs-ofctl add-flow ap1 "priority=0,icmp,in_port=1,'
                'actions=output:in_port,normal"')
        ap1.cmd('ovs-ofctl add-flow ap1 "priority=0,udp,in_port=1,'
                'actions=output:in_port,normal"')
        ap1.cmd('ovs-ofctl add-flow ap1 "priority=0,tcp,in_port=1,'
                'actions=output:in_port,normal"')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('debug')
    topology()
