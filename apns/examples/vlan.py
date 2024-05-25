#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller


def topology():
    "Create a network."
    net = Wmnet(controller=Controller)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1')
    sta2 = net.addSta('sta2')
    sta3 = net.addSta('sta3')
    sta4 = net.addSta('sta4')
    ap1 = net.addAP('ap1', ssid="ssid-ap1",
                             mode="g", channel="5",
                             failMode="standalone")
    ap2 = net.addAP('ap2', ssid="ssid-ap2",
                             mode="g", channel="11",
                             failMode="standalone")

    info("--- Links\n")
    net.addLink(ap1, ap2)
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap1)
    net.addLink(sta3, ap2)
    net.addLink(sta4, ap2)

    info("--- Start\n")
    net.build()
    ap1.start([])
    ap2.start([])

    sta1.cmd("ip link add link sta1-wlan0 name sta1-wlan0.10 type vlan id 10")
    sta2.cmd("ip link add link sta2-wlan0 name sta2-wlan0.10 type vlan id 10")
    sta3.cmd("ip link add link sta3-wlan0 name sta3-wlan0.20 type vlan id 20")
    sta4.cmd("ip link add link sta4-wlan0 name sta4-wlan0.20 type vlan id 20")

    sta1.cmd("route del -net 10.0.0.0 netmask 255.0.0.0")
    sta2.cmd("route del -net 10.0.0.0 netmask 255.0.0.0")
    sta3.cmd("route del -net 10.0.0.0 netmask 255.0.0.0")
    sta4.cmd("route del -net 10.0.0.0 netmask 255.0.0.0")

    sta1.cmd("ifconfig sta1-wlan0.10 10.0.0.1")
    sta2.cmd("ifconfig sta2-wlan0.10 10.0.0.2")
    sta3.cmd("ifconfig sta3-wlan0.20 10.0.0.3")
    sta4.cmd("ifconfig sta4-wlan0.20 10.0.0.4")

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
