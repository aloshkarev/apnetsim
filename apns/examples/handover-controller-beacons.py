#!/usr/bin/python

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import RemoteController, UserSwitch, UserAP
from apns.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Wmnet(controller=RemoteController, accessPoint=UserAP,
                switch=UserSwitch, link=wmediumd,
                wmediumd_mode=interference)

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
    s4 = net.addSwitch('s4')
    h1 = net.addHost('h1')
    controller_ = net.addHost('con', ip='10.0.0.100/8', inNamespace=False)
    c1 = net.addController('c1', controller=RemoteController, ip='127.0.0.1')

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    net.plotGraph(max_x=300, max_y=300)

    info("--- Links\n")
    net.addLink(h1, ap1)
    net.addLink(s4, ap1)
    net.addLink(s4, ap2)
    net.addLink(s4, ap3)
    net.addLink(s4, controller_)

    info("--- Start\n")
    net.build()
    net.addNAT().configDefault()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])
    ap3.start([c1])
    s4.start([c1])

    sta1.cmd('iw dev sta1-wlan0 interface add mon0 type monitor')
    sta1.cmd('ifconfig mon0 up')
    sta2.cmd('iw dev sta2-wlan0 interface add mon0 type monitor')
    sta2.cmd('ifconfig mon0 up')
    sta1.cmd('wpa_cli -i sta1-wlan0 roam 00:00:00:00:00:01')
    sta2.cmd('wpa_cli -i sta2-wlan0 roam 00:00:00:00:00:01')
    sta1.cmd('./sta1_1.py &')
    sta2.cmd('./sta2_1.py &')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
