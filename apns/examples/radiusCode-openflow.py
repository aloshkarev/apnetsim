#!/usr/bin/python

import os

from apns.cli import CLI
from apns.link import wmediumd
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import RemoteController
from apns.wmediumdConnector import interference


def topology():
    "Create a network."
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    net.addSta('sta1', ip='192.168.0.1',
                   radius_passwd='sdnteam', encrypt='wpa2',
                   radius_identity='joe', position='110,120,0')
    net.addSta('sta2', ip='192.168.0.2',
                   radius_passwd='hello', encrypt='wpa2',
                   radius_identity='bob', position='200,100,0')
    ap1 = net.addSta('ap1', ip='192.168.0.100',
                         position='150,100,0')
    h1 = net.addHost('h1', ip='10.0.0.100/8')
    s1 = net.addSwitch('s1')
    c0 = net.addController('c0', controller=RemoteController,
                           ip='127.0.0.1', port=6653)

    info("--- Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3.5)

    ap1.setMasterMode(intf='ap1-wlan0', ssid='ap1-ssid', channel='1',
                      mode='n', authmode='8021x', encrypt='wpa2',
                      radius_server='10.0.0.100')

    info("--- Links\n")
    net.addLink(ap1, s1)
    net.addLink(s1, h1)

    info("--- Start\n")
    net.build()
    c0.start()
    s1.start([c0])

    ap1.cmd('ifconfig ap1-eth2 10.0.0.200')
    ap1.cmd('ifconfig ap1-wlan0 0')

    h1.cmdPrint('rc.radiusd start')
    ap1.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
    # s1.cmd('ovs-ofctl add-flow s1 in_port=1,priority=65535,'
    # dl_type=0x800,nw_proto=17,tp_dst=1812,actions=2,controller')

    info("--- CLI\n")
    CLI(net)

    os.system('pkill radiusd')

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
