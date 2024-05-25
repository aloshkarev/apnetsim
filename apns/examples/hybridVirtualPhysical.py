#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, physicalAP


def topology():
    "Create a network."
    net = Wmnet(controller=Controller)

    usbDongleIface = 'wlxf4f26d193319'

    info("--- Create Network Elements\n")
    net.addSta('sta1', mac='00:00:00:00:00:01',
                   ip='192.168.0.1/24', position='10,10,0')
    phyap1 = net.addAP('phyap1', ssid='ssid-ap1',
                                mode='g', channel='1',
                                position='50,50,0', phywlan=usbDongleIface,
                                cls=physicalAP)
    c0 = net.addController('c0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    net.plotGraph(max_x=240, max_y=240)

    info("--- Start\n")
    net.build()
    c0.start()
    phyap1.start([c0])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
