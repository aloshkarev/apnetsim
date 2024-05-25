#!/usr/bin/env python

"""
This example shows on how to create wireless link between two APs with mesh
The wireless mesh network is based on IEEE 802.11s
"""

from apns.cli import CLI
from apns.link import wmediumd, mesh
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:11', position='1,1,0')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:12', position='31,11,0')
    ap1 = net.addAP('ap1', wlans=2, ssid='ssid1', position='10,10,0')
    ap2 = net.addAP('ap2', wlans=2, ssid='ssid2', position='30,10,0')
    c0 = net.addController('c0')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap2)
    net.addLink(ap1, intf='ap1-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)
    net.addLink(ap2, intf='ap2-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)

    info("--- Start\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
