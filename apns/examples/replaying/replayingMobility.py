#!/usr/bin/python

import os

from apns.cli import CLI
from apns.link import wmediumd, adhoc
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller
from apns.replaying import ReplayingMobility
from apns.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:02',
                          ip='10.0.0.1/8', speed=4)
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:03',
                          ip='10.0.0.2/8', speed=6)
    sta3 = net.addSta('sta3', mac='00:00:00:00:00:04',
                          ip='10.0.0.3/8', speed=3)
    sta4 = net.addSta('sta4', mac='00:00:00:00:00:05',
                          ip='10.0.0.4/8', speed=3)
    ap1 = net.addAP('ap1', ssid='new-ssid',
                             mode='g', channel='1',
                             position='45,45,0')
    c1 = net.addController('c1', controller=Controller)

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(sta3, cls=adhoc, intf='sta3-wlan0', ssid='adhocNet')
    net.addLink(sta4, cls=adhoc, intf='sta4-wlan0', ssid='adhocNet')

    path = os.path.dirname(os.path.abspath(__file__))
    getTrace(sta1, '%s/replayingMobility/node1.dat' % path)
    getTrace(sta2, '%s/replayingMobility/node2.dat' % path)
    getTrace(sta3, '%s/replayingMobility/node3.dat' % path)
    getTrace(sta4, '%s/replayingMobility/node4.dat' % path)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])

    ReplayingMobility(net)

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


def getTrace(sta, file_):
    file_ = open(file_, 'r')
    raw_data = file_.readlines()
    file_.close()

    sta.p = []
    pos = (-1000, 0, 0)
    sta.position = pos

    for data in raw_data:
        line = data.split()
        x = line[0]  # First Column
        y = line[1]  # Second Column
        pos = x, y, 0
        sta.p.append(pos)


if __name__ == '__main__':
    setLogLevel('info')
    topology()
