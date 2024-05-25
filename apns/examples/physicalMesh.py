#!/usr/bin/env python

"""This example shows how to work with physical mesh nodes"""

import os

from apns.cli import CLI
from apns.link import wmediumd, mesh, physicalMesh
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)
    # intf: physical interface
    intf = 'wlxf4f26d193319'

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', position='10,10,0', inNamespace=False)
    sta2 = net.addSta('sta2', position='50,10,0')
    sta3 = net.addSta('sta3', position='90,10,0')

    net.setPropagationModel(model="logDistance", exp=4)

    info("--- Links\n")
    net.addLink(sta1, cls=physicalMesh, intf=intf,
                ssid='meshNet', channel=5)
    net.addLink(sta2, cls=mesh, intf='sta2-wlan0',
                ssid='meshNet', channel=5)
    net.addLink(sta3, cls=mesh, intf='sta3-wlan0',
                ssid='meshNet', channel=5)

    net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()

    # This is the interface/ip addr of the physical node
    os.system('ip addr add 10.0.0.4/8 dev physta1-mp0')

    info("--- CLI\n")
    CLI(net)

    # Delete the interface created previously
    os.system('iw dev physta1-mp0 del')

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
