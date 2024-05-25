#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller


def topology():
    "Create a network."
    net = Wmnet(controller=Controller)

    info("--- Create Network Elements\n")
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='g',
                             channel='1', position='10,10,0')
    net.addSta('sta1', position='10,20,0')
    c1 = net.addController('c1', controller=Controller)

    info("--- Start\n")
    net.build()
    net.addNAT().configDefault()
    c1.start()
    ap1.start([c1])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
