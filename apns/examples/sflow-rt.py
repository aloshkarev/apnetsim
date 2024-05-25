#!/usr/bin/python

import re
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
    "Create a network."
    net = Wmnet(link=wmediumd, wmediumd_mode=interference)

    info("--- Create Network Elements\n")
    sta1 = net.addSta('sta1', mac='00:00:00:00:00:11', position='1,1,0')
    sta2 = net.addSta('sta2', mac='00:00:00:00:00:12', position='31,11,0')
    ap1 = net.addAP('ap1', wlans=2, ssid=['ssid1', 'mesh'], position='10,10,0')
    ap2 = net.addAP('ap2', wlans=2, ssid=['ssid2', 'mesh'], position='30,10,0')
    ap3 = net.addAP('ap3', wlans=2, ssid=['ssid3', 'mesh'], position='50,10,0')
    c0 = net.addController('c0')

    info("--- Links\n")
    net.addLink(sta1, ap1)
    net.addLink(sta2, ap2)

    info("--- Creating mesh links\n")
    net.addLink(ap1, intf='ap1-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)
    net.addLink(ap2, intf='ap2-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)
    net.addLink(ap3, intf='ap3-wlan2', cls=mesh, ssid='mesh-ssid', channel=5)

    info("--- Building network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    ap2.start([c0])
    ap3.start([c0])

    ap1.cmd('iw dev %s-mp2 interface add %s-mon0 type monitor' %
            (ap1.name, ap1.name))
    ap2.cmd('iw dev %s-mp2 interface add %s-mon0 type monitor' %
            (ap2.name, ap2.name))
    ap1.cmd('ifconfig %s-mon0 up' % ap1.name)
    ap2.cmd('ifconfig %s-mon0 up' % ap2.name)

    ifname = 'enp2s0'  # have to be changed to your own iface!
    collector = environ.get('COLLECTOR', '127.0.0.1')
    sampling = environ.get('SAMPLING', '10')
    polling = environ.get('POLLING', '10')
    sflow = 'ovs-vsctl -- --id=@sflow create sflow agent=%s target=%s ' \
            'sampling=%s polling=%s --' % (ifname, collector, sampling, polling)

    for ap in net.aps:
        sflow += ' -- set bridge %s sflow=@sflow' % ap
        info(' '.join([ap.name for ap in net.aps]))
        quietRun(sflow)

    agent = '127.0.0.1'
    topo = {'nodes': {}, 'links': {}}
    for ap in net.aps:
        topo['nodes'][ap.name] = {'agent': agent, 'ports': {}}

    path = '/sys/devices/virtual/aprf_drv/'
    for child in listdir(path):
        dir_ = '/sys/devices/virtual/aprf_drv/' + '%s' % child + '/net/'
        for child_ in listdir(dir_):
            node = child_[:3]
            if node in topo['nodes']:
                ifindex = open(dir_ + child_ + '/ifindex').read().split('\n', 1)[0]
                topo['nodes'][node]['ports'][child_] = {'ifindex': ifindex}

    path = '/sys/devices/virtual/net/'
    for child in listdir(path):
        parts = re.match('(^.+)-(.+)', child)
        if parts is None: continue
        if parts.group(1) in topo['nodes']:
            ifindex = open(path + child + '/ifindex').read().split('\n', 1)[0]
            topo['nodes'][parts.group(1)]['ports'][child] = {'ifindex': ifindex}

    linkName = '%s-%s' % (ap1.name, ap2.name)
    topo['links'][linkName] = {'node1': ap1.name, 'port1': 'ap1-mp2',
                               'node2': ap2.name, 'port2': 'ap2-mp2'}
    linkName = '%s-%s' % (ap2.name, ap3.name)
    topo['links'][linkName] = {'node1': ap2.name, 'port1': 'ap2-mp2',
                               'node2': ap3.name, 'port2': 'ap3-mp2'}
    linkName = '%s-%s' % (ap1.name, ap2.name)
    topo['links'][linkName] = {'node1': ap1.name, 'port1': ap1.wintfs[0].name,
                               'node2': ap2.name, 'port2': ap2.wintfs[0].name}

    put('http://127.0.0.1:8008/topology/json', data=dumps(topo))

    info("--- CLI\n")
    CLI(net)

    info("--- Stop\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()
