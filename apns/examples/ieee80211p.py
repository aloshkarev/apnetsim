#!/usr/bin/env python

"""
NOTE: you have to install wireless-regdb and CRDA
      please refer to https://mininet-wifi.github.io/80211p/
"""

from apns.cli import CLI
from apns.link import wmediumd, ITSLink
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', ip='10.0.0.1/8', position='100,150,0')
    sta2 = net.addSta('sta2', ip='10.0.0.2/8', position='150,150,0')
    sta3 = net.addSta('sta3', ip='10.0.0.3/8', position='200,150,0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    info("--- Plotting Graph\n")
    net.plotGraph(max_x=300, max_y=300)

    info("--- Starting ITS Links\n")
    net.addLink(sta1, intf='sta1-wlan0', cls=ITSLink,
                band=20, channel=181, proto='batman_adv')
    net.addLink(sta2, intf='sta2-wlan0', cls=ITSLink,
                band=20, channel=181, proto='batman_adv')
    net.addLink(sta3, intf='sta3-wlan0', cls=ITSLink,
                band=20, channel=181, proto='batman_adv')

    info("--- Start\n")
    net.build()

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
