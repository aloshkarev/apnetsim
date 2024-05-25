#!/usr/bin/env python

'''
A sanity check for cluster edition
'''

from apns.examples.cluster import WmnetCluster
from apns.examples.clustercli import ClusterCLI as CLI
from apns.log import setLogLevel
from apns.topo import SingleSwitchTopo


def clusterSanity():
    "Sanity check for cluster mode"
    topo = SingleSwitchTopo()
    net = WmnetCluster(topo=topo)
    net.start()
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    clusterSanity()
