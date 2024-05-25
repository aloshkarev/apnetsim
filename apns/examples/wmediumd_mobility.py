#!/usr/bin/env python

"""
Setting the position of Nodes (only for Stations and Access Points)
and providing mobility using mobility models with wmediumd enabled."""

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology(args):
    """Create a network."""
    net = Wmnet(bridge_with="enp3s0")

    info("--- Create Network Elements\n")
    ap1 = net.addAP('ap1',
                             position='150,150,0')
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8')
    c1 = net.addController('c1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    net.plotGraph(max_x=300, max_y=300)

    net.setMobilityModel(time=0, model='RandomDirection', max_x=300, max_y=300,
                         min_v=0.5, max_v=0.8, seed=20)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start()

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('debug')
    topology(sys.argv)
