#!/usr/bin/python

import sys

from apns.cli import CLI
from apns.link import wmediumd, mesh
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.wmediumdConnector import interference


def topology(mobility):
    "Create a network."
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    if mobility:
        sta1 = net.addSta('sta1')
        sta2 = net.addSta('sta2')
        sta3 = net.addSta('sta3')
    else:
        sta1 = net.addSta('sta1', position='10,10,0')
        sta2 = net.addSta('sta2', position='50,10,0')
        sta3 = net.addSta('sta3', position='90,10,0')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4)

    info("--- Links\n")
    net.addLink(sta1, cls=mesh, ssid='meshNet',
                intf='sta1-wlan0', channel=5)  # , passwd='thisisreallysecret')
    net.addLink(sta2, cls=mesh, ssid='meshNet',
                intf='sta2-wlan0', channel=5)  # , passwd='thisisreallysecret')
    net.addLink(sta3, cls=mesh, ssid='meshNet',
                intf='sta3-wlan0', channel=5)  # , passwd='thisisreallysecret')

    if mobility:
        net.plotGraph(max_x=100, max_y=100)
        net.startMobility(time=0, model='RandomDirection',
                          max_x=100, max_y=100,
                          min_v=0.5, max_v=0.8, seed=20)

    net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    mobility = True if '-m' in sys.argv else False
    topology(mobility)
