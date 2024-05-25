#!/usr/bin/python

import sys

from apns.cli import CLI
from apns.link import wmediumd, adhoc
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology(autoTxPower):
    "Create a network."
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    if autoTxPower:
        sta1 = net.addSta('sta1', position='10,10,0', range=100)
        sta2 = net.addSta('sta2', position='50,10,0', range=100)
        sta3 = net.addSta('sta3', position='90,10,0', range=100)
    else:
        sta1 = net.addSta('sta1', position='10,10,0')
        sta2 = net.addSta('sta2', position='50,10,0')
        sta3 = net.addSta('sta3', position='90,10,0')

    net.setPropagationModel(model="logDistance", exp=4)

    info("--- Links\n")
    net.addLink(sta1, intf='sta1-wlan0', cls=adhoc, ssid='adhocNet',
                mode='g', channel=5, ht_cap='HT40+')
    net.addLink(sta2, intf='sta2-wlan0', cls=adhoc, ssid='adhocNet',
                mode='g', channel=5)
    net.addLink(sta3, intf='sta3-wlan0', cls=adhoc, ssid='adhocNet',
                mode='g', channel=5, ht_cap='HT40+')

    info("--- Start\n")
    net.build()

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    autoTxPower = True if '-a' in sys.argv else False
    topology(autoTxPower)
