#!/usr/bin/env python

"""
Regression test for pty leak in Node()
"""

import unittest

from apns.clean import cleanup
from apns.net import Wmnet
from apns.topo import SingleSwitchTopo


class TestPtyLeak(unittest.TestCase):
    """Verify that there is no pty leakage"""

    @staticmethod
    def testPtyLeak():
        """Test for pty leakage"""
        net = Wmnet(SingleSwitchTopo())
        net.start()
        host = net['h1']
        for _ in range(0, 10):
            oldptys = host.slave, host.master
            net.delHost(host)
            host = net.addHost('h1')
            assert (host.slave, host.master) == oldptys
        net.stop()


if __name__ == '__main__':
    unittest.main()
    cleanup()
