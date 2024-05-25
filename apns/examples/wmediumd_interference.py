#!/usr/bin/env python

"""Setting the position of Nodes with wmediumd to calculate the interference"""

import sys

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology(args):
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference,
                noise_th=-91, fading_cof=3)

    info("--- Create Network Elements\n")
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='a', channel='36',
                             position='15,30,0')
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.1/8',
                   position='10,20,0')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.2/8',
                   position='20,50,0')
    net.addSta('sta3', mac='00:00:00:00:00:04', ip='10.0.0.3/8',
                   position='20,60,10')
    c1 = net.addController('c1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4)

    if '-p' not in args:
        net.plotGraph(max_x=100, max_y=100)

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
