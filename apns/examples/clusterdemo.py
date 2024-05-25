#!/usr/bin/python

"clusterdemo.py: demo of Wmnet Cluster Edition prototype"

from apns.examples.cluster import WmnetCluster, SwitchBinPlacer
from apns.examples.clustercli import ClusterCLI as CLI
from apns.log import setLogLevel
from apns.topolib import TreeTopo


def demo():
    "Simple Demo of Cluster Mode"
    servers = ['localhost', 'ubuntu2', 'ubuntu3']
    topo = TreeTopo(depth=3, fanout=3)
    net = WmnetCluster(topo=topo, servers=servers,
                       placement=SwitchBinPlacer)
    net.start()
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    demo()
