#!/usr/bin/python

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, OVSKernelAP
from apns.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Wmnet(controller=Controller, link=wmediumd,
                accessPoint=OVSKernelAP, wmediumd_mode=interference,
                noise_th=-91, fading_cof=3)

    info("--- Create Network Elements\n")
    ap1 = net.addAP('ap1', ssid='ap1', mode='n',
                             channel='1', position='15,30,0')
    ap2 = net.addAP('ap2', ssid='ap2', mode='n',
                             channel='6', position='35,30,0')
    ap3 = net.addAP('ap3', ssid='ap3', mode='n',
                             channel='11', position='55,30,0')
    net.addSta('sta1', mac='00:00:00:00:00:10', ip='10.0.0.1/8',
                   position='30,30,0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=5)

    net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()
    ap1.start([])
    ap2.start([])
    ap3.start([])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
