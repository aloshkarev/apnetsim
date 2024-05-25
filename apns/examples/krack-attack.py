#!/usr/bin/python

import os

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import WmnetWithControlWNet
from apns.node import RemoteController, UserAP
from apns.wmediumdConnector import interference


def topology():
    info("--- Shutting down any controller running on port 6653\n")
    os.system('sudo fuser -k 6653/tcp')

    "Create a network."
    net = WmnetWithControlWNet(controller=RemoteController, accessPoint=UserAP,
                               link=wmediumd, wmediumd_mode=interference,
                               inNamespace=True)

    info("--- Create Network Elements\n")
    net.addSta('sta1', ip='10.0.0.1/8', position='20,0,0', inNamespace=False)
    ap1 = net.addAP('ap1', mac='02:00:00:00:00:01', ssid="handover", mode="g",
                             channel="1", ieee80211r='yes', mobility_domain='a1b2',
                             passwd='123456789a', encrypt='wpa2', position='10,30,0',
                             inNamespace=True)
    ap2 = net.addAP('ap2', mac='02:00:00:00:00:02', ssid="handover", mode="g",
                             channel="6", ieee80211r='yes', mobility_domain='a1b2',
                             passwd='123456789a', encrypt='wpa2', position='100,30,0',
                             inNamespace=True)
    c1 = net.addController('c1', controller=RemoteController, port=6653)

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    info("--- Linking nodes\n")
    net.addLink(ap1, ap2)

    'plotting graph'
    net.plotGraph(min_x=-100, min_y=-100, max_x=200, max_y=200)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])

    ap1.cmd('ifconfig ap1-wlan1 10.0.0.101/8')
    ap2.cmd('ifconfig ap2-wlan1 10.0.0.102/8')
    os.system('ip link set wemu0 up')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
