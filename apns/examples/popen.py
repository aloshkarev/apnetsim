#!/usr/bin/python

"""
This example monitors a number of hosts using host.popen() and
pmonitor()
"""

from apns.log import setLogLevel
from apns.net import Wmnet
from apns.node import CPULimitedHost
from apns.topo import SingleSwitchTopo
from apns.util import custom, pmonitor


def monitorhosts(hosts=5, sched='cfs'):
    "Start a bunch of pings and monitor them using popen"
    mytopo = SingleSwitchTopo(hosts)
    cpu = .5 / hosts
    myhost = custom(CPULimitedHost, cpu=cpu, sched=sched)
    net = Wmnet(topo=mytopo, host=myhost)
    net.start()
    # Start a bunch of pings
    popens = {}
    last = net.hosts[-1]
    for host in net.hosts:
        popens[host] = host.popen("ping -c5 %s" % last.IP())
        last = host
    # Monitor them and print output
    for host, line in pmonitor(popens):
        if host:
            print(("<%s>: %s" % (host.name, line.strip())))
    # Done
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    monitorhosts(hosts=5)
