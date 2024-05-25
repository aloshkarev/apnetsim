#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller, UserAP


def topology():
    "Create a network."
    net = Wmnet(controller=Controller, accessPoint=UserAP)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', passwd='123456789a', encrypt='wpa2')
    net.addSta('sta2')
    ap1 = net.addAP('ap1', ssid="ap1-ssid", mode="g", channel="1",
                             passwd='123456789a', encrypt='wpa2',
                             failMode="standalone")

    info("--- Links\n")
    net.addLink(sta1, ap1)

    info("--- Start\n")
    net.build()
    ap1.start([])

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
