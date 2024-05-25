#!/usr/bin/python

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology():
    net = Wmnet()

    info("--- Create Network Elements\n")
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='0/0', position='30,60,0')
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='g', channel='1',
                             position='50,50,0', failMode='standalone')
    h1 = net.addHost('h1', ip='192.168.11.1/24', inNamespace=False)

    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(ap1, h1)

    net.plotGraph(max_x=100, max_y=100)

    info("--- Start\n")
    net.build()
    ap1.start([])

    h1.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
