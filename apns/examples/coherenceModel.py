#!/usr/bin/env python

"""Setting the position of Nodes and providing mobility using mobility models"""
import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology(args):
    """Create a network."""
    net = Wmnet()

    info("--- Create Network Elements\n")
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8')
    ap1 = net.addAP('ap1', wlans=2, ssid='ssid1,ssid2', mode='g',
                             channel='1', failMode="standalone",
                             position='50,50,0')

    if '-p' not in args:
        net.plotGraph(max_x=300, max_y=300)

    net.setMobilityModel(time=1, model='CRP',
                         pointlist=[(100, 11, 0), (101, 12, 0), (102, 13, 0), (103, 14, 0), (104, 15, 0), (105, 16, 0),
                                    (106, 17, 0), (107, 18, 0), (108, 19, 0), (109, 20, 0), (110, 21, 0), (111, 22, 0)])

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
