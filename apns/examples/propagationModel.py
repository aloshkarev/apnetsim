#!/usr/bin/env python

"""This example show how to configure Propagation Models"""

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology(args):
    """Create a network."""
    net = Wmnet()

    info("--- Create Network Elements\n")
    net.addSta('sta1', antennaHeight='1', antennaGain='5')
    net.addSta('sta2', antennaHeight='1', antennaGain='5')
    ap1 = net.addAP('ap1', ssid='new-ssid', model='DI524',
                             mode='g', channel='1', position='50,50,0')
    c1 = net.addController('c1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4)
    if '-p' not in args:
        net.plotGraph(max_x=100, max_y=100)

    net.setMobilityModel(time=0, model='RandomWayPoint', max_x=100, max_y=100,
                         min_v=0.5, max_v=0.5, seed=20)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)
