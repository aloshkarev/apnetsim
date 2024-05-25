#!/usr/bin/python

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import RemoteController


def topology(qos):
    "Create a network."
    net = Wmnet(controller=RemoteController)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', position='10,10,0')
    h1 = net.addHost('h1')
    ap1 = net.addAP('ap1', ssid="simplewifi", position='10,20,0',
                             mode="g", channel="5", protocols='OpenFlow13',
                             datapath='user')
    c0 = net.addController('c0')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(h1, ap1)

    info("--- Start\n")
    net.build()
    c0.start()
    ap1.start([c0])

    if qos:
        ap1.cmdPrint('ovs-ofctl -O OpenFlow13 add-meter ap1 '
                     '\'meter=1,kbps,bands=type=drop,rate=5000\'')
        ap1.cmdPrint('ovs-ofctl -O OpenFlow13 add-flow ap1 '
                     '\'priority=1,in_port=1 action=meter:1,2\'')
        ap1.cmdPrint('ovs-ofctl -O OpenFlow13 add-flow ap1 '
                     '\'priority=1,in_port=2 action=meter:1,1\'')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    qos = True if '-q' in sys.argv else False
    topology(qos)
