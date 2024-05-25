#!/usr/bin/env python

from json import dumps
from os import listdir, environ

from requests import put

from apns.cli import CLI
from apns.link import wmediumd, mesh
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.util import quietRun
from apns.wmediumdConnector import interference


def topology():
    """Create a network."""
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:11', position='1,1,0')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:12', position='91,11,0')
    ap1 = net.addAP('ap1', wlans=2, ssid='ssid1', failMode='standalone',
                             position='10,10,0')
    ap2 = net.addAP('ap2', wlans=2, ssid='ssid2', failMode='standalone',
                             position='50,10,0')
    ap3 = net.addAP('ap3', wlans=2, ssid='ssid3', failMode='standalone',
                             position='90,10,0')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap3)
    net.addLink(ap1, intf='ap1-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)
    net.addLink(ap2, intf='ap2-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)
    net.addLink(ap3, intf='ap3-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)

    info("--- Start\n")
    net.start()

    info("--- Sending data to sflow-rt\n")
    sflow_rt(net.aps)

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


def sflow_rt(aps):
    ifname = 'lo'
    collector = environ.get('COLLECTOR', '127.0.0.1')
    sampling = environ.get('SAMPLING', '10')
    polling = environ.get('POLLING', '10')
    sflow = 'ovs-vsctl -- --id=@sflow create sflow agent=%s target=%s ' \
            'sampling=%s polling=%s --' % (ifname, collector, sampling, polling)

    for ap in aps:
        sflow += ' -- set bridge %s sflow=@sflow' % ap
        quietRun(sflow)

    agent = '127.0.0.1'
    topo = {'nodes': {}, 'links': {}}
    for ap in aps:
        topo['nodes'][ap.name] = {'agent': agent, 'ports': {}}

    path = '/sys/devices/virtual/aprf_drv/'
    # /sys/devices/virtual/net/ can be used in place of the path above
    for child in listdir(path):
        dir_ = path + '{}'.format(child + '/net/')
        for child_ in listdir(dir_):
            node = child_[:3]
            if node in topo['nodes']:
                ifindex = open(dir_ + child_ + '/ifindex').read().split('\n', 1)[0]
                topo['nodes'][node]['ports'][child_] = {'ifindex': ifindex}

    for id, ap1 in enumerate(aps):
        if id < len(aps) - 1:
            ap2 = aps[id + 1]
            linkName = '{}-{}'.format(ap1.name, ap2.name)
            topo['links'][linkName] = {'node1': ap1.name, 'port1': ap1.wintfs[1].name,
                                       'node2': ap2.name, 'port2': ap2.wintfs[1].name}

    put('http://127.0.0.1:8008/topology/json', data=dumps(topo))


if __name__ == '__main__':
    setLogLevel('info')
    topology()
