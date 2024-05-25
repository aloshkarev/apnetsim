#!/usr/bin/env python

"""Setting the position of nodes and providing mobility"""

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology(args):
    """Create a network."""
    net = Wmnet()

    info("--- Create Network Elements\n")
    h1 = net.addHost('h1', mac='00:00:00:00:00:01', ip='10.0.0.1/8')
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8')
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='g', channel='1',
                             position='45,40,0')
    c1 = net.addController('c1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(ap1, h1)

    if '-p' not in args:
        net.plotGraph(max_x=200, max_y=200)

    if '-c' in args:
        sta1.coord = ['40.0,30.0,0.0', '31.0,10.0,0.0', '31.0,30.0,0.0']
        sta2.coord = ['40.0,40.0,0.0', '55.0,31.0,0.0', '55.0,81.0,0.0']

    net.startMobility(time=0, mob_rep=1, reverse=False)

    p1, p2, p3, p4 = {}, {}, {}, {}
    if '-c' not in args:
        p1 = {'position': '40.0,30.0,0.0'}
        p2 = {'position': '40.0,40.0,0.0'}
        p3 = {'position': '31.0,10.0,0.0'}
        p4 = {'position': '55.0,31.0,0.0'}

    net.mobility(sta1, 'start', time=1, **p1)
    net.mobility(sta2, 'start', time=2, **p2)
    net.mobility(sta1, 'stop', time=12, **p3)
    net.mobility(sta2, 'stop', time=22, **p4)
    net.stopMobility(time=23)

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
