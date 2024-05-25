#!/usr/bin/python

"""This example shows how to work with Radius Server"""

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, UserAP
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(controller=Controller, accessPoint=UserAP,
                link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', radius_passwd='sdnteam', encrypt='wpa2',
                          radius_identity='joe', position='110,120,0')
    sta2 = net.addSta('sta2', radius_passwd='hello', encrypt='wpa2',
                          radius_identity='bob', position='200,100,0')
    ap1 = net.addAP('ap1', ssid='simplewifi', authmode='8021x',
                             mode='a', channel='36', encrypt='wpa2', position='150,100,0')
    c0 = net.addController('c0', controller=Controller, ip='127.0.0.1', port=6653)

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)

    net.plotGraph(max_x=300, max_y=300)

    info("--- Start\n")
    net.build()
    c0.start()
    ap1.start([c0])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
