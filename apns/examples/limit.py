#!/usr/bin/python

"""
limit.py: example of using link and CPU limits
"""

from apns.link import TCIntf
from apns.log import setLogLevel, info
from apns.net import Wmnet
from apns.node import CPULimitedHost
from apns.topolib import TreeTopo
from apns.util import custom, quietRun


def testLinkLimit(net, bw):
    "Run bandwidth limit test"
    info('--- Testing network %.2f Mbps bandwidth limit\n' % bw)
    net.iperf()


def limit(bw=10, cpu=.1):
    """Example/test of link and CPU bandwidth limits
       bw: interface bandwidth limit in Mbps
       cpu: cpu limit as fraction of overall CPU time"""
    intf = custom(TCIntf, bw=bw)
    myTopo = TreeTopo(depth=1, fanout=2)
    for sched in 'rt', 'cfs':
        info('--- Testing with', sched, 'bandwidth limiting\n')
        if sched == 'rt':
            release = quietRun('uname -r').strip('\r\n')
            output = quietRun('grep CONFIG_RT_GROUP_SCHED /boot/config-%s'
                              % release)
            if output == '# CONFIG_RT_GROUP_SCHED is not set\n':
                info('--- RT Scheduler is not enabled in your kernel. '
                     'Skipping this test\n')
                continue
        host = custom(CPULimitedHost, sched=sched, cpu=cpu)
        net = Wmnet(topo=myTopo, intf=intf, host=host)
        net.start()
        testLinkLimit(net, bw=bw)
        net.runCpuLimitTest(cpu=cpu)
        net.stop()


def verySimpleLimit(bw=150):
    "Absurdly simple limiting test"
    intf = custom(TCIntf, bw=bw)
    net = Wmnet(intf=intf)
    h1, h2 = net.addHost('h1'), net.addHost('h2')
    net.addLink(h1, h2)
    net.start()
    net.pingAll()
    net.iperf()
    h1.cmdPrint('tc -s qdisc ls dev', h1.defaultIntf())
    h2.cmdPrint('tc -d class show dev', h2.defaultIntf())
    h1.cmdPrint('tc -s qdisc ls dev', h1.defaultIntf())
    h2.cmdPrint('tc -d class show dev', h2.defaultIntf())
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    limit()
