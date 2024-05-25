#!/usr/bin/python

import os
from sys import version_info as py_version_info

from apns.cli import CLI
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import Controller
from apns.replaying import ReplayingNetworkConditions


def topology():
    "Create a network."
    net = Wmnet(controller=Controller)

    info("--- Create Network Elements")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:01',
                          ip='192.168.0.1/24',
                          position='47.28,50,0')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:02',
                          ip='192.168.0.2/24',
                          position='54.08,50,0')
    ap3 = net.addAP('ap3', ssid='ap-ssid3', mode='g',
                             channel='1', position='50,50,0')
    c0 = net.addController('c0', controller=Controller, port=6653)

    info("--- Start")
    net.build()
    c0.start()
    ap3.start([c0])

    sta1.cmd('iw dev sta1-wlan0 interface add mon0 type monitor &')
    sta1.cmd('ifconfig mon0 up &')
    sta2.cmd('iw dev sta2-wlan0 interface add mon0 type monitor &')
    sta2.cmd('ifconfig mon0 up &')
    if py_version_info < (3, 0):
        sta2.cmd('pushd ~/Downloads; python -m SimpleHTTPServer 80 &')
    else:
        sta2.cmd('pushd ~/Downloads; python -m http.server 80 &')

    path = os.path.dirname(os.path.abspath(__file__))
    getTrace(sta1, '%s/replayingNetworkConditions/clientTrace.txt' % path)
    getTrace(sta2, '%s/replayingNetworkConditions/serverTrace.txt' % path)

    ReplayingNetworkConditions.addNode(sta1)
    ReplayingNetworkConditions.addNode(sta2)
    ReplayingNetworkConditions(net)

    info("--- CLI")
    CLI(net)

    info("--- Stop")
    net.stop()


def getTrace(sta, file):
    file = open(file, 'r')
    raw_data = file.readlines()
    file.close()

    sta.time = []
    sta.bw = []
    sta.loss = []
    sta.delay = []
    sta.latency = []

    for data in raw_data:
        line = data.split()
        sta.time.append(float(line[0]))  # First Column = Time
        sta.bw.append(((float(line[1])) / 1000000) / 2)  # Second Column = BW
        sta.loss.append(float(line[2]))  # second Column = LOSS
        sta.latency.append(float(line[3]))  # Second Column = LATENCY


if __name__ == '__main__':
    setLogLevel('info')
    topology()
