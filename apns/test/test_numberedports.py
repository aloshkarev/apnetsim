#!/usr/bin/env python

"""
Test for numberedports.py
"""

import unittest

import pexpect

from apns.node import OVSSwitch


class testNumberedports(unittest.TestCase):

    @unittest.skipIf(OVSSwitch.setup() or OVSSwitch.isOldOVS(), "old version of OVS")
    def testConsistency(self):
        """verify consistency between apns and ovs ports"""
        p = pexpect.spawn('python -m apns.examples.numberedports')
        opts = ['Validating that s1-eth\d is actually on port \d ... Validated.',
                'Validating that s1-eth\d is actually on port \d ... WARNING',
                pexpect.EOF]
        correct_ports = True
        count = 0
        while True:
            index = p.expect(opts)
            if index == 0:
                count += 1
            elif index == 1:
                correct_ports = False
            elif index == 2:
                self.assertNotEqual(0, count)
                break
        self.assertTrue(correct_ports)

    def testNumbering(self):
        """verify that all of the port numbers are printed correctly and consistent with their interface"""
        p = pexpect.spawn('python -m apns.examples.numberedports')
        opts = ['s1-eth(\d+) :  (\d+)',
                pexpect.EOF]
        count_intfs = 0
        while True:
            index = p.expect(opts)
            if index == 0:
                count_intfs += 1
                intfport = p.match.group(1)
                ofport = p.match.group(2)
                self.assertEqual(intfport, ofport)
            elif index == 1:
                break
                self.assertNotEqual(0, count_intfs)


if __name__ == '__main__':
    unittest.main()
