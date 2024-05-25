#!/usr/bin/env python

"""This example shows how to work with active scan"""

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import UserAP


def topology():
    """Create a network."""
    net = Wmnet(accessPoint=UserAP)

    info("--- Create Network Elements\n")
    net.addSta('sta1', passwd='123456789a,123456789a', encrypt='wpa2,wpa2',
                   wlans=2, active_scan=1, scan_freq='2412,2437',
                   freq_list='2412,2437', position='5,10,0')
    net.addSta('sta2', passwd='123456789a', encrypt='wpa2',
                   active_scan=1, scan_freq='2437', freq_list='2437',
                   position='45,10,0')
    ap1 = net.addAP('ap1', ssid="ssid-1", mode="g", channel="1",
                             passwd='123456789a', encrypt='wpa2',
                             position='10,10,0')
    ap2 = net.addAP('ap2', ssid="ssid-1", mode="g", channel="6",
                             passwd='123456789a', encrypt='wpa2',
                             position='40,10,0')
    c0 = net.addController('c0')

    net.plotGraph(max_x=120, max_y=120)

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
