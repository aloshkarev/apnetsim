#!/usr/bin/python

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import RemoteController, UserAP
from apns.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Wmnet(controller=RemoteController, accessPoint=UserAP,
                link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', position='15,20,0')
    sta2 = net.addSta('sta2', position='35,20,0')
    ap1 = net.addAP('ap1', mac='00:00:00:00:00:01', ssid="handover",
                             mode="g", channel="1", passwd='123456789a',
                             encrypt='wpa2', position='10,30,0')
    ap2 = net.addAP('ap2', mac='00:00:00:00:00:02', ssid="handover",
                             mode="g", channel="6", passwd='123456789a',
                             encrypt='wpa2', position='60,30,0')
    ap3 = net.addAP('ap3', mac='00:00:00:00:00:03', ssid="handover",
                             mode="g", channel="1", passwd='123456789a',
                             encrypt='wpa2', position='120,100,0')
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    h3 = net.addHost('h3')
    c1 = net.addController('c1', controller=RemoteController)

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    info("--- Links\n")
    net.addLink(ap1, ap2)
    net.addLink(ap2, ap3)
    net.addLink(h1, ap1)
    net.addLink(h2, ap2)
    net.addLink(h3, ap3)

    net.plotGraph(min_x=-100, min_y=-100, max_x=200, max_y=200)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])
    ap3.start([c1])

    sta1.cmd('wpa_cli -i sta1-wlan0 roam 00:00:00:00:00:01')
    sta2.cmd('wpa_cli -i sta2-wlan0 roam 00:00:00:00:00:01')
    sta1.cmd('./sta1_2.py &')
    sta2.cmd('./sta2_2.py &')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
