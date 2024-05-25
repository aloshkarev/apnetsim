#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, OVSKernelAP


def topology():
    "Create a network."
    net = Wmnet(controller=Controller, accessPoint=OVSKernelAP)

    info("--- Create Network Elements\n")
    net.addSta('sta1', position='10,10,0')
    ap1 = net.addAP('ap1', ssid='ssid-ap1', mode='g', channel='1',
                             position='15,30,0', range=30)
    ap2 = net.addAP('ap2', ssid='ssid-ap2', mode='g', channel='6',
                             position='55,30,0', range=30)
    s3 = net.addSwitch('s3')
    h1 = net.addHost('h1')
    c1 = net.addController('c1', controller=Controller)

    net.setPropagationModel(model="logDistance", exp=5)

    info("--- Links\n")
    net.addLink(ap1, s3)
    net.addLink(ap2, s3)
    net.addLink(s3, h1)

    net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])
    s3.start([c1])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
