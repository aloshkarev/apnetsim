#!/usr/bin/env python

"""
Tests for baresshd.py
"""

import unittest

import pexpect

from apns.clean import cleanup, Cleanup


class testBareSSHD(unittest.TestCase):
    opts = ['Welcome to h1', pexpect.EOF, pexpect.TIMEOUT]

    def connected(self):
        "Log into ssh server, check banner, then exit"
        p = pexpect.spawn('ssh 10.0.0.1 -o StrictHostKeyChecking=no -i /tmp/ssh/test_rsa exit')
        while True:
            index = p.expect(self.opts)
            if index == 0:
                return True
            else:
                return False

    def setUp(self):
        # verify that sshd is not running
        self.assertFalse(self.connected())
        # create public key pair for testing
        Cleanup.sh('rm -rf /tmp/ssh')
        Cleanup.sh('mkdir /tmp/ssh')
        Cleanup.sh("ssh-keygen -t rsa -P '' -f /tmp/ssh/test_rsa")
        Cleanup.sh('cat /tmp/ssh/test_rsa.pub >> /tmp/ssh/authorized_keys')
        # run example with custom sshd args
        cmd = ('python -m apns.examples.baresshd '
               '-o AuthorizedKeysFile=/tmp/ssh/authorized_keys '
               '-o StrictModes=no')
        p = pexpect.spawn(cmd)
        runOpts = ['You may now ssh into h1 at 10.0.0.1',
                   'after 5 seconds, h1 is not listening on port 22',
                   pexpect.EOF, pexpect.TIMEOUT]
        while True:
            index = p.expect(runOpts)
            if index == 0:
                break
            else:
                self.tearDown()
                self.fail('sshd failed to start in host h1')

    def testSSH(self):
        "Simple test to verify that we can ssh into h1"
        result = False
        # try to connect up to 3 times; sshd can take a while to start
        result = self.connected()
        self.assertTrue(result)

    def tearDown(self):
        # kill the ssh process
        Cleanup.sh("ps aux | grep 'ssh.*Banner' | awk '{ print $2 }' | xargs kill")
        cleanup()
        # remove public key pair
        Cleanup.sh('rm -rf /tmp/ssh')


if __name__ == '__main__':
    unittest.main()
