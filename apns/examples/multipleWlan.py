#!/usr/bin/python

from __future__ import print_function

from apns.cli import CLI
from apns.link import adhoc
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology():
    "Create a network."
    net = Wmnet()

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', wlans=2)
    sta2 = net.addSta('sta2')
    ap1 = net.addAP('ap1', ssid='ssid_1', mode='g', channel='5',
                             failMode="standalone")

    info("--- Associating...\n")
    net.addLink(ap1, sta1)
    net.addLink(sta1, intf='sta1-wlan0', cls=adhoc, ssid='adhoc1')
    net.addLink(sta2, intf='sta2-wlan0', cls=adhoc, ssid='adhoc1')

    info("--- Start\n")
    net.build()
    ap1.start([])

    info("--- Addressing...\n")
    sta1.setIP('192.168.10.1/24', intf="sta1-wlan1")
    sta2.setIP('192.168.10.2/24', intf="sta2-wlan0")

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
