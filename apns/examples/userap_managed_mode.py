#!/usr/bin/env python

"""This example creates a simple network topology with 2 APs working in mesh mode"""

from apns.cli import CLI
from apns.link import wmediumd, mesh
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, UserAP
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(controller=Controller, link=wmediumd,
                wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addAP('sta1', ip='192.168.0.1/24',
                              position='10,10,0', cls=UserAP, inNamespace=True)
    sta2 = net.addAP('sta2', ip='192.168.0.2/24',
                              position='10,20,0', cls=UserAP, inNamespace=True)
    c0 = net.addController('c0')

    info("--- Links\n")
    net.addLink(sta1, intf='sta1-wlan1', cls=mesh,
                ssid='mesh-ssid', channel=5)
    net.addLink(sta2, intf='sta2-wlan1', cls=mesh,
                ssid='mesh-ssid', channel=5)

    info("--- Start\n")
    net.build()
    c0.start()
    sta1.start([c0])
    sta2.start([c0])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
