#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller


def topology():
    "Create a network."
    net = Wmnet(controller=Controller, ac_method='ssf')

    info("--- Create Network Elements\n")
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8', position='20,50,0')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8', position='25,50,0')
    net.addSta('sta3', mac='00:00:00:00:00:04', ip='10.0.0.4/8', position='35,50,0')
    net.addSta('sta4', mac='00:00:00:00:00:05', ip='10.0.0.5/8', position='40,50,0')
    net.addSta('sta5', mac='00:00:00:00:00:06', ip='10.0.0.6/8', position='45,50,0')
    ap1 = net.addAP('ap1', ssid='ssid-ap1', mode='g', channel='1',
                             position='50,50,0')
    ap2 = net.addAP('ap2', ssid='ssid-ap2', mode='g', channel='6',
                             position='70,50,0', range=30)
    c1 = net.addController('c1')

    net.setPropagationModel(model="logDistance", exp=5)

    info("--- Links\n")
    net.addLink(ap1, ap2)

    net.plotGraph(max_x=120, max_y=120)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
