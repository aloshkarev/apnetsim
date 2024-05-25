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
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8',
                   min_x=10, max_x=30, min_y=50, max_y=70, min_v=5, max_v=10)
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8',
                   min_x=60, max_x=70, min_y=10, max_y=20, min_v=1, max_v=5)
    if '-m' in args:
        ap1 = net.addAP('ap1', wlans=2, ssid='ssid1,ssid2', mode='g',
                                 channel='1', failMode="standalone",
                                 position='50,50,0')
    else:
        ap1 = net.addAP('ap1', ssid='new-ssid', mode='g', channel='1',
                                 failMode="standalone", position='50,50,0')

    if '-p' not in args:
        net.plotGraph()

    net.setMobilityModel(time=0, model='RandomDirection',
                         max_x=100, max_y=100, seed=20)

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
