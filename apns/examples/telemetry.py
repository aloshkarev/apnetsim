#!/usr/bin/env python

"""This uses telemetry() to enable a graph with live statistics"""

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(controller=Controller, link=wmediumd,
                wmediumd_mode=interference,
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

    nodes = net.stations
    net.telemetry(nodes=nodes, single=True, data_type='rssi')

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
    topology()
