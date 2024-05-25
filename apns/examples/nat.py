#!/usr/bin/python

"""
Example to create a Wmnet topology and connect it to the internet via NAT
"""

from apns.cli import CLI
from apns.log import lg
from apns.topolib import TreeNet

if __name__ == '__main__':
    lg.setLogLevel('info')
    net = TreeNet(depth=1, fanout=4)
    # Add NAT connectivity
    net.addNAT().configDefault()
    net.start()
    print("--- Hosts are running and should have internet connectivity")
    print("--- Type 'exit' or control-D to shut down network")
    CLI(net)
    # Shut down NAT
    net.stop()
