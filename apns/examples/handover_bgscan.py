#!/usr/bin/env python

""" Handover example supported by bgscan (Background scanning) and wmediumd.

ieee 802.11r can be enabled adding the parameters below:

ieee80211r='yes'
mobility_domain='a1b2'

e.g. ap1 = net.addAP('ap1', ..., ieee80211r='yes',
mobility_domain='a1b2',...)

Consider https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf
for more information about bgscan"""

import sys

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, UserAP
from apns.wmediumdConnector import interference


def topology(args):
    """Create a network."""
    net = Wmnet(controller=Controller, accessPoint=UserAP,
                link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    net.addSta('sta1', position='15,20,0', bgscan_threshold=-60,
                   s_inverval=5, l_interval=10, bgscan_module="simple")
    ap1 = net.addAP('ap1', mac='00:00:00:00:00:01', ssid="handover",
                             mode="g", channel="1", passwd='123456789a',
                             encrypt='wpa2', position='10,30,0')
    ap2 = net.addAP('ap2', mac='00:00:00:00:00:02', ssid="handover",
                             mode="g", channel="6", passwd='123456789a',
                             encrypt='wpa2', position='60,30,0')
    ap3 = net.addAP('ap3', mac='00:00:00:00:00:03', ssid="handover",
                             mode="g", channel="1", passwd='123456789a',
                             encrypt='wpa2', position='120,100,0')
    c1 = net.addController('c1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    info("--- Links\n")
    net.addLink(ap1, ap2)
    net.addLink(ap2, ap3)

    if '-p' not in args:
        net.plotGraph(min_x=-100, min_y=-100, max_x=200, max_y=200)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])
    ap3.start([c1])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)
