#!/usr/bin/env python

"""Example for WiFi Direct"""

import sys
from time import sleep

from apns.cli import CLI
from apns.link import wmediumd, WifiDirectLink
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology(args):
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference,
                configWiFiDirect=True)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', ip='10.0.0.1/8', position='10,10,0')
    sta2 = net.addSta('sta2', ip='10.0.0.2/8', position='20,20,0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    if '-p' not in args:
        net.plotGraph(max_x=200, max_y=200)

    info("--- Starting WiFi Direct\n")
    net.addLink(sta1, intf='sta1-wlan0', cls=WifiDirectLink)
    net.addLink(sta2, intf='sta2-wlan0', cls=WifiDirectLink)

    info("--- Start\n")
    net.build()

    sta1.cmd('wpa_cli -ista1-wlan0 p2p_find')
    sta2.cmd('wpa_cli -ista2-wlan0 p2p_find')
    sta2.cmd('wpa_cli -ista2-wlan0 p2p_peers')
    sleep(3)
    sta1.cmd('wpa_cli -ista1-wlan0 p2p_peers')
    sleep(3)
    pin = sta1.cmd('wpa_cli -ista1-wlan0 p2p_connect %s pin auth'
                   % sta2.wintfs[0].mac)
    sleep(3)
    sta2.cmd('wpa_cli -ista2-wlan0 p2p_connect %s %s'
             % (sta1.wintfs[0].mac, pin))

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)
