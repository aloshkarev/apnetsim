#!/usr/bin/python

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import OVSBridgeAP


def topology(stp):
    net = Wmnet(accessPoint=OVSBridgeAP)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.1/8',
                          position='100,101,0')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.2/8',
                          position='50,51,0')
    sta3 = net.addSta('sta3', mac='00:00:00:00:00:04', ip='10.0.0.3/8',
                          position='150,51,0')
    if stp:
        ap1 = net.addAP('ap1', ssid='new-ssid1', mode='g', channel='1',
                                 failMode="standalone", position='100,100,0',
                                 stp=True)
        ap2 = net.addAP('ap2', ssid='new-ssid2', mode='g', channel='1',
                                 failMode="standalone", position='50,50,0',
                                 stp=True)
        ap3 = net.addAP('ap3', ssid='new-ssid3', mode='g', channel='1',
                                 failMode="standalone", position='150,50,0',
                                 stp=True)
    else:
        ap1 = net.addAP('ap1', ssid='new-ssid1', mode='g', channel='1',
                                 failMode="standalone", position='100,100,0')
        ap2 = net.addAP('ap2', ssid='new-ssid2', mode='g', channel='1',
                                 failMode="standalone", position='50,50,0')
        ap3 = net.addAP('ap3', ssid='new-ssid3', mode='g', channel='1',
                                 failMode="standalone", position='150,50,0')

    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(ap1, sta1)
    net.addLink(ap2, sta2)
    net.addLink(ap3, sta3)
    net.addLink(ap1, ap2)
    net.addLink(ap1, ap3)
    net.addLink(ap2, ap3)

    net.plotGraph(max_x=300, max_y=300)

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
    stp = True if '-s' in sys.argv else False
    topology(stp)
