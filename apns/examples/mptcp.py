#!/usr/bin/python

import sys

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller


def topology(is_mptcp):
    "Create a network."
    net = Wmnet(controller=Controller)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', wlans=2, position='51,10,0')
    ap1 = net.addAP('ap1', mac='00:00:00:00:00:02', ssid='ssid_ap1',
                             mode='g', channel='6', position='55,17,0')
    ap2 = net.addAP('ap2', mac='00:00:00:00:00:03',
                             ssid='ssid_ap2', mode='n', channel='1',
                             position='50,11,0')
    r1 = net.addHost('r1', mac='00:00:00:00:00:04')
    h1 = net.addHost('h1', mac='00:00:00:00:00:10')
    c1 = net.addController('c1')

    info("--- Links\n")
    net.addLink(ap1, sta1, 0, 0)
    net.addLink(ap2, sta1, 0, 1)
    net.addLink(ap1, r1, bw=1000)
    net.addLink(ap2, r1, bw=1000)
    net.addLink(r1, h1, bw=100)
    net.addLink(r1, h1, bw=100)

    info("--- Start\n")
    net.build()
    c1.start()
    ap1.start([c1])
    ap2.start([c1])

    r1.cmd('ifconfig r1-eth0 10.0.0.1/24')
    r1.cmd('ifconfig r1-eth1 10.0.1.1/24')
    r1.cmd('ifconfig r1-eth2 10.0.2.1/24')
    r1.cmd('ifconfig r1-eth3 10.0.3.1/24')

    h1.cmd('ifconfig h1-eth0 10.0.2.2/24')
    h1.cmd('ifconfig h1-eth1 10.0.3.2/24')

    sta1.cmd('ifconfig sta1-wlan0 10.0.0.2/24')
    sta1.cmd('ifconfig sta1-wlan1 10.0.1.2/24')

    sta1.cmd("ip rule add from 10.0.0.2 table 1")
    sta1.cmd("ip rule add from 10.0.1.2 table 2")
    sta1.cmd("ip route add 10.0.0.0/24 dev sta1-wlan0 scope link table 1")
    sta1.cmd("ip route add default via 10.0.0.1 dev sta1-wlan0 table 1")
    sta1.cmd("ip route add 10.0.1.0/24 dev sta1-wlan1 scope link table 2")
    sta1.cmd("ip route add default via 10.0.1.1 dev sta1-wlan1 table 2")
    sta1.cmd("ip route add default scope global nexthop via 10.0.0.1 dev sta1-wlan0")

    h1.cmd("ip rule add from 10.0.2.2 table 1")
    h1.cmd("ip rule add from 10.0.3.2 table 2")
    h1.cmd("ip route add 10.0.2.0/24 dev h1-eth0 scope link table 1")
    h1.cmd("ip route add default via 10.0.2.1 dev h1-eth0 table 1")
    h1.cmd("ip route add 10.0.3.0/24 dev h1-eth1 scope link table 2")
    h1.cmd("ip route add default via 10.0.3.1 dev h1-eth1 table 2")
    h1.cmd("ip route add default scope global nexthop via 10.0.2.1 dev h1-eth0")

    r1.cmd('sysctl -w net.ipv4.ip_forward=1')

    if not is_mptcp:
        sta1.cmd('iw dev sta1-wlan1 disconnect')

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    is_mptcp = True if '-m' in sys.argv else False
    topology(is_mptcp)
