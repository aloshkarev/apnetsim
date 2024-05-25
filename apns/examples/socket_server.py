#!/usr/bin/python

'Setting position of the nodes and enable sockets'

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet


def topology():
    net = Wmnet()

    info("--- Create Network Elements\n")
    net.addSta('sta1', mac='00:00:00:00:00:02', ip='10.0.0.1/8',
                   position='30,60,0')
    net.addSta('sta2', mac='00:00:00:00:00:03', ip='10.0.0.2/8',
                   position='70,30,0')
    ap1 = net.addAP('ap1', ssid='new-ssid', mode='g', channel='1',
                             failMode="standalone", position='50,50,0')
    h1 = net.addHost('h1', ip='10.0.0.3/8')

    net.setPropagationModel(model="logDistance", exp=4.5)

    info("--- Links\n")
    net.addLink(ap1, h1)

    info("--- Start\n")
    net.addNAT(linkTo='ap1').configDefault()
    net.build()
    ap1.start([])

    # set_socket_ip: localhost must be replaced by ip address
    # of the network interface of your system
    # The same must be done with socket_client.py
    info("--- Starting Socket Server\n")
    net.socketServer(ip='127.0.0.1', port=12345)

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
