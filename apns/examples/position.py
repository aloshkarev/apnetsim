#!/usr/bin/env python

"""Setting position of the nodes"""

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology(args):
    net = Wmnet()

    info("--- Create Network Elements\n")
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='g', channel='1',
                             failMode="standalone", mac='00:00:00:00:00:01',
                             position='50,50,0')
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.1/8',
                   position='30,60,0')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.2/8',
                   position='70,30,0')
    h1 = net.addHost('h1', ip='10.0.0.3/8')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(ap1, h1)

    if '-p' not in args:
        net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()
    ap1.start([])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)
