#!/usr/bin/python


from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology():
    "Create a network."
    net = Wmnet()

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', passwd='1234567891a', encrypt='wep')
    sta2 = net.addSta('sta2', passwd='123456789a', encrypt='wep')
    sta3 = net.addSta('sta3', passwd='123456789a', encrypt='wep')
    ap1 = net.addAP('ap1', ssid="simplewifi", mode="g", channel="1",
                             passwd='123456789a', encrypt='wep',
                             failMode="standalone", datapath='user')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)
    net.addLink(sta3, ap1)

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
