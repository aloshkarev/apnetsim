#!/usr/bin/python

"""
Create a 1024-host network, and run the CLI on it.
If this fails because of kernel limits, you may have
to adjust them, e.g. by adding entries to /etc/sysctl.conf
and running sysctl -p. Check util/sysctl_addon.
"""

from apns.cli import CLI
from apns.log import setLogLevel
from apns.node import OVSSwitch
from apns.topolib import TreeNet

if __name__ == '__main__':
    setLogLevel('info')
    network = TreeNet(depth=2, fanout=32, switch=OVSSwitch)
    network.run(CLI, network)
