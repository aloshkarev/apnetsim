#!/usr/bin/env python

"""
Tests for the Wmnet Walkthrough
TODO: missing xterm test
"""
import os
import re
import unittest
from time import sleep

import pexpect

from apns.util import quietRun


def tsharkVersion():
    """Return tshark version"""
    versionStr = quietRun('tshark -v')
    versionMatch = re.findall(r'TShark \d+.\d+.\d+', versionStr)[0]
    return versionMatch.split()[1]


# pylint doesn't understand pexpect.match, unfortunately!
# pylint:disable=maybe-no-member


class testWalkthrough(unittest.TestCase):
    """Test Wmnet walkthrough"""

    prompt = 'mn-wifi>'

    # PART 1
    def testHelp(self):
        """Check the usage message"""
        p = pexpect.spawn('mn --wifi -h')
        sleep(5)
        index = p.expect(['Usage: mn', pexpect.EOF])
        self.assertEqual(index, 0)

    def testBasic(self):
        """Test basic CLI commands (help, nodes, net, dump)"""
        p = pexpect.spawn('mn --wifi')
        sleep(8)
        p.expect(self.prompt)
        # help command
        p.sendline('help')
        index = p.expect(['commands', self.prompt])
        self.assertEqual(index, 0, 'No output for "help" command')
        # nodes command
        p.sendline('nodes')
        p.expect(r'(ap\B\d ?){1}([c]\d ?){1}(sta\B\d ?){2}')
        nodes = p.match.group(0).split()
        self.assertEqual(len(nodes), 4, 'No nodes in "nodes" command')
        p.expect(self.prompt)
        # net command
        p.sendline('net')
        expected = [x for x in nodes]
        while len(expected) > 0:
            index = p.expect(expected)
            node = p.match.group(0)
            expected.remove(node)
            p.expect('\n')
        self.assertEqual(len(expected), 0, '"nodes" and "net" differ')
        p.expect(self.prompt)
        # dump command
        p.sendline('dump')
        expected = [r'<\w+ (%s)' % n for n in nodes]
        actual = []
        for _ in nodes:
            index = p.expect(expected)
            node = p.match.group(1)
            actual.append(node)
            p.expect('\n')
        self.assertEqual(actual.sort(), nodes.sort(),
                         '"nodes" and "dump" differ')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('mn --wifi --position')
        sleep(5)
        p.expect(self.prompt)
        p.sendline('py sta1.position')
        p.expect('[1.0, 0.0, 0.0]')
        p.expect(self.prompt)
        p.sendline('py sta2.position')
        p.expect('[3.0, 0.0, 0.0]')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testConnectivity(self):
        """Test ping and pingall"""
        p = pexpect.spawn('mn --wifi')
        p.expect(self.prompt)
        sleep(8)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('pingall')
        p.expect('0% dropped')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testModes(self):
        """Test wireless modes"""
        p = pexpect.spawn('mn --wifi')
        p.expect(self.prompt)
        sleep(8)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep type')
        p.expect('managed')
        p.expect(self.prompt)
        p.sendline('ap1 iw dev wlan0 info | grep type')
        p.expect('AP')
        p.expect(self.prompt)
        p.sendline('py sta1.setMasterMode(intf=\'sta1-wlan0\')')
        p.expect(self.prompt)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep type')
        p.expect('AP')
        p.expect(self.prompt)
        p.sendline('py sta1.setAdhocMode(intf=\'sta1-wlan0\')')
        p.expect(self.prompt)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep type')
        p.expect('IBSS')
        p.expect(self.prompt)
        p.sendline('py sta1.setMeshMode(intf=\'sta1-wlan0\')')
        p.expect(self.prompt)
        p.sendline('sta1 iw dev sta1-mp0 info | grep type')
        p.expect('mesh point')
        p.expect(self.prompt)
        p.sendline('py ap1.setAdhocMode(intf=\'ap1-wlan1\')')
        p.expect(self.prompt)
        p.sendline('ap1 iw dev wlan0 info | grep type')
        p.expect('IBSS')
        p.expect(self.prompt)
        p.sendline('py ap1.setMeshMode(intf=\'wlan0\')')
        p.expect(self.prompt)
        p.sendline('ap1 iw dev ap1-mp1 info | grep type')
        p.expect('mesh point')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testPythonInterpreter(self):
        """Test py and px by checking IP for sta1 and adding sta3"""
        p = pexpect.spawn('mn --wifi')
        p.expect(self.prompt)
        # test station IP
        p.sendline('py sta1.IP()')
        p.expect('10.0.0.1')
        p.expect(self.prompt)
        # test adding host
        p.sendline("px net.addSta('sta3')")
        p.expect(self.prompt)
        p.sendline("px net.addLink(ap1, sta3)")
        p.expect(self.prompt)
        p.sendline('net')
        p.expect('sta3')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('mn --wifi --link=wmediumd --position')
        p.expect(self.prompt)
        # test station IP
        p.sendline("px net.addSta('sta3', position=\'10,10,0\')")
        p.expect(self.prompt)
        p.sendline('py sta3.position')
        p.expect('[10.0, 10.0, 0.0]')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testSimpleHTTP(self):
        """Start an HTTP server on sta1 and wget from sta2"""
        p = pexpect.spawn('mn --wifi')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('sta1 python -m http.server 80 &')
        p.expect(self.prompt)
        p.sendline(' sta2 wget -O - sta1')
        p.expect('200 OK')
        p.expect(self.prompt)
        p.sendline('sta1 kill %python')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    # PART 2
    def testRegressionRun(self):
        """Test pingpair (0% drop) and iperf (bw > 0) regression tests"""
        # test pingpair
        p = pexpect.spawn('mn --wifi --test pingpair')
        p.expect('0% dropped')
        p.expect(pexpect.EOF)
        # test iperf
        p = pexpect.spawn('mn --wifi --test iperf')
        p.expect(r"Results: \['([\d\.]+) .bits/sec',")
        bw = float(p.match.group(1))
        self.assertTrue(bw > 0)
        p.expect(pexpect.EOF)

    def testTopoChange(self):
        """Test pingall on single,3 and linear,4 topos"""
        # testing single,3
        p = pexpect.spawn('mn --wifi --test pingall --topo single,3')
        p.expect(r'(\d+)/(\d+) received')
        received = int(p.match.group(1))
        sent = int(p.match.group(2))
        self.assertEqual(sent, 6, 'Wrong number of pings sent in single,3')
        self.assertEqual(sent, received, 'Dropped packets in single,3')
        p.expect(pexpect.EOF)
        # testing linear,4
        p = pexpect.spawn('mn --wifi --test pingall --topo linear,4')
        p.expect(r'(\d+)/(\d+) received')
        received = int(p.match.group(1))
        sent = int(p.match.group(2))
        self.assertTrue(sent > 10)  # it should be 12, but there is a delay
        # for association
        p.expect(pexpect.EOF)

    def testLinkChange(self):
        """Test TCLink bw and delay"""
        p = pexpect.spawn('mn --wifi --link wtc,bw=10,delay=10ms')
        # test bw
        sleep(8)
        p.expect(self.prompt)
        p.sendline('iperf')
        p.expect(r"Results: \['([\d\.]+) Mbits/sec',")
        bw = float(p.match.group(1))
        self.assertTrue(bw > 10.1, 'Bandwidth > 10 Mb/s')
        p.expect(self.prompt)
        # test delay
        p.sendline('sta1 ping -c4 sta2')
        p.expect(r'rtt min/avg/max/mdev = '
                 r'([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms')
        delay = float(p.match.group(2))
        self.assertTrue(delay > 20, 'Delay < 20ms')
        self.assertTrue(delay < 25, 'Delay > 20ms')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testVerbosity(self):
        """Test debug and output verbosity"""
        # test output
        p = pexpect.spawn('mn --wifi -v output')
        sleep(8)
        p.expect(self.prompt)
        self.assertEqual(len(p.before), 0, 'Too much output for "output"')
        p.sendline('exit')
        p.wait()
        # test debug
        p = pexpect.spawn('mn --wifi -v debug --test none')
        sleep(8)
        p.expect(pexpect.EOF)
        lines = p.before.split('\n')
        self.assertTrue(len(lines) > 70, "Debug output is too short")

    def testCustomTopo(self):
        """Start Wmnet using a custom topo, then run pingall"""
        # Satisfy pylint
        assert self
        custom = os.path.dirname(os.path.realpath(__file__))
        custom = os.path.join(custom, '../examples/topo-2ap-2sta.py')
        custom = os.path.normpath(custom)
        p = pexpect.spawn(
            'mn --wifi --custom %s --topo mytopo --test pingall' % custom)
        sleep(20)
        p.expect('0% dropped')
        p.expect(pexpect.EOF)

    def testStaticMAC(self):
        """Verify that MACs are set correctly"""
        p = pexpect.spawn('mn --wifi --mac')
        sleep(8)
        p.expect(self.prompt)
        for i in range(1, 3):
            p.sendline('sta%d ip addr show' % i)
            p.expect(r'\s00:00:00:00:00:0%d\s' % i)
            p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testBenchmark(self):
        """Run benchmark and verify that it takes less than 4 seconds"""
        p = pexpect.spawn('mn --wifi --test none')
        sleep(3)
        p.expect(r'completed in ([\d\.]+) seconds')
        time = float(p.match.group(1))
        self.assertTrue(time < 4, 'Benchmark takes more than 4 seconds')

    def testOwnNamespace(self):
        """Test running user ap in its own namespace"""
        pexpect.spawn('mn -c')
        p = pexpect.spawn('mn --wifi --innamespace --ap user')
        sleep(8)
        p.expect(self.prompt)
        interfaces = ['sta1-wlan0', 'ap1-wlan1', '[^-]eth0', 'lo',
                      self.prompt]
        p.sendline('ap1 ip addr show')
        ifcount = 0
        while True:
            index = p.expect(interfaces)
            if index == 1 or index == 3:
                ifcount += 1
            elif index == 0:
                self.fail('sta1 interface displayed in "ap1 ip addr show"')
            elif index == 2:
                self.fail('wlan0 displayed in "ap1 ip addr show"')
            else:
                break
        # self.assertEqual( ifcount, 2, 'Missing interfaces on ap1' )
        # verify that all stations a reachable
        p.sendline('pingall')
        p.expect(r'(\d+)% dropped')
        dropped = int(p.match.group(1))
        self.assertEqual(dropped, 0, 'pingall failed')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testLink(self):
        """Test link CLI command using ping"""
        p = pexpect.spawn('mn --wifi')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('link ap1 sta1 down')
        p.expect(self.prompt)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('100% packet loss')
        p.expect(self.prompt)
        p.sendline('link ap1 sta1 up')
        p.expect(self.prompt)
        sleep(8)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('0% packet loss')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testAssociationControl(self):
        """Start mn-wifi with association control"""
        p = pexpect.spawn('python -m apns.examples.associationControl')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('sta10 iw dev sta10-wlan0 link | grep Connected')
        p.expect('00:00:00:00:01:00')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('python -m apns.examples.associationControl -llf')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('sta10 iw dev sta10-wlan0 link | grep Connected')
        p.expect('00:00:00:00:02:00')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testMultipleWlan(self):
        """Start mn-wifi with multiple WLAN"""
        p = pexpect.spawn('python -m apns.examples.multipleWlan')
        sleep(8)
        p.sendline('sta1 ip addr show sta1-wlan0')
        p.expect('sta1-wlan0')
        p.expect(self.prompt)
        p.sendline('sta1 ip addr show sta1-wlan1')
        p.expect('sta1-wlan1')
        p.expect(self.prompt)
        p.sendline('sta1 ip addr show sta1-wlan2')
        p.expect('sta1-wlan2')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testPosition(self):
        """Start mn-wifi when the position is statically defined,
        then test ping"""
        p = pexpect.spawn('python -m apns.examples.position -p')
        sleep(8)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('py sta1.setPosition(\'500,500,0\')')
        p.expect(self.prompt)
        p.sendline('sta1 iw dev sta1-wlan0 link')
        p.expect('Not connected')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testUserAPManagedMode(self):
        """Start mn-wifi with userap in mesh mode"""
        p = pexpect.spawn('python -m apns.examples.userap_managed_mode')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testMobility(self):
        """Start mn-wifi using mobility, then test ping"""
        p = pexpect.spawn('python -m apns.examples.mobility -p')
        sleep(8)
        p.sendline('sta1 ping -c 1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testMobilityModel(self):
        """Start mn-wifi using mobility model, then test attr"""
        p = pexpect.spawn('python -m apns.examples.mobilityModel -m -p')
        sleep(8)
        p.sendline('py ap1.wintfs')
        wlans = ['ap1-wlan1', 'ap1-wlan2']
        p.expect(wlans)
        p.expect(self.prompt)
        p.sendline('py ap1.wintfs[0].stationsInRange')
        stas = ['Station sta1', 'Station sta2']
        p.expect(stas)
        p.expect(self.prompt)
        p.sendline('py ap1.wintfs[0].ssid')
        ssid = 'ssid1'
        p.expect(ssid)
        p.sendline('py ap1.wintfs[1].ssid')
        ssid = 'ssid2'
        p.expect(ssid)
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testVirtualIface(self):
        """Start mn-wifi using simplewifitopology, then test vif"""
        p = pexpect.spawn('python -m apns.examples.simplewifitopology -v')
        sleep(8)
        wlans = ['sta1-wlan0', 'sta1-wlan01', 'sta1-wlan02', self.prompt]
        p.sendline('py sta1.wintfs')
        p.expect(wlans)
        p.sendline('exit')
        p.wait()

    def testPropagationModel(self):
        """Start mn-wifi using a propagation model, then test ping and rssi"""
        p = pexpect.spawn('python -m apns.examples.propagationModel -p')
        sleep(8)
        p.sendline('sta1 ping -c 1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testReplayingMobility(self):
        """Start mn-wifi using Replaying Mobility, then test ping"""
        p = pexpect.spawn(
            'python -m apns.examples.replaying.replayingMobility -p')
        sleep(10)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('sta3 ping -c1 sta4')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testAuthentication(self):
        """Start mn-wifi using WPA, then test ping"""
        p = pexpect.spawn('python -m apns.examples.authentication')
        sleep(10)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testHandover(self):
        """Start mn-wifi with handover, then test handover"""
        p = pexpect.spawn('python -m apns.examples.handover -p')
        sleep(10)
        p.expect(self.prompt)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep ssid')
        p.expect('ssid-ap1')
        p.expect(self.prompt)
        sleep(8)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep ssid')
        p.expect('ssid-ap2')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('python -m apns.examples.handover -s -p')
        sleep(8)
        p.expect(self.prompt)
        p.sendline('py ap1.wintfs[0].associatedStations')
        p.expect('managed sta1-wlan0')
        p.expect(self.prompt)
        p.sendline('py ap1.wintfs[0].stationsInRange')
        p.expect('Station sta1')
        p.expect(self.prompt)
        p.sendline('py ap2.wintfs[0].associatedStations')
        p.expect('managed sta2-wlan0')
        p.expect(self.prompt)
        p.sendline('py ap2.wintfs[0].stationsInRange')
        p.expect('Station sta2')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].ssid')
        p.expect('ssid-ap1')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].apsInRange')
        p.expect('OVSAP ap1')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].associatedTo')
        p.expect('master ap1-wlan1')
        p.expect(self.prompt)
        p.sendline('py sta2.wintfs[0].ssid')
        p.expect('ssid-ap2')
        p.expect(self.prompt)
        p.sendline('py sta2.wintfs[0].apsInRange')
        p.expect('OVSAP ap2')
        p.expect(self.prompt)
        p.sendline('py sta2.wintfs[0].associatedTo')
        p.expect('master ap2-wlan1')
        p.expect(self.prompt)
        p.sendline('py sta1.setPosition(\'40,30,0\')')
        p.sendline('py ap1.wintfs[0].associatedStations')
        p.expect('managed sta1-wlan0')
        p.expect(self.prompt)
        p.sendline('py ap1.wintfs[0].stationsInRange')
        p.expect('Station sta1')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].ssid')
        p.expect('ssid-ap1')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].apsInRange')
        aps = ['OVSAP ap1', 'OVSAP ap2']
        p.expect(aps)
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].associatedTo')
        p.expect('master ap1-wlan1')
        p.expect(self.prompt)
        p.sendline('py sta1.setPosition(\'70,30,0\')')
        p.sendline('py sta1.wintfs[0].ssid')
        p.expect('ssid-ap2')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].apsInRange')
        p.expect('OVSAP ap2')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].associatedTo')
        p.expect('master ap2-wlan1')
        p.expect(self.prompt)
        stas = ['sta1-wlan0', 'sta2-wlan0']
        p.sendline('py ap2.wintfs[0].associatedStations')
        p.expect(stas)
        p.expect(self.prompt)
        p.sendline('py ap2.wintfs[0].stationsInRange')
        p.expect(stas)
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testMutipleSSID(self):
        """Start mn-wifi with multiple SSIDs, then test connectivity"""
        pexpect.spawn(
            'service network-manager stop')
        p = pexpect.spawn(
            'python -m apns.examples.forwardingBySSID -p')
        sleep(8)
        p.sendline('sta1 iw dev sta1-wlan0 info | grep ssid')
        p.expect('ssid1')
        p.expect(self.prompt)
        p.sendline('sta2 iw dev sta2-wlan0 info | grep ssid')
        p.expect('ssid2')
        p.expect(self.prompt)
        p.sendline('sta3 iw dev sta3-wlan0 info | grep ssid')
        p.expect('ssid2')
        p.expect(self.prompt)
        p.sendline('sta4 iw dev sta4-wlan0 info | grep ssid')
        p.expect('ssid3')
        p.expect(self.prompt)
        p.sendline('sta5 iw dev sta5-wlan0 info | grep ssid')
        p.expect('ssid4')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdErrorProb(self):
        """Start mn-wifi, then test wmediumd_error_prob.py"""
        pexpect.spawn(
            'service network-manager stop')
        p = pexpect.spawn(
            'python -m apns.examples.wmediumd_error_prob -p')
        sleep(10)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('sta1 ping -c1 sta3')
        p.expect('1 packets transmitted, 0 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdWiFiDirect(self):
        """Start mn-wifi using wifi direct, then test ping"""
        pexpect.spawn(
            'service network-manager stop')
        p = pexpect.spawn('python -m apns.examples.wifiDirect -p')
        sleep(17)
        p.sendline('pingall')
        p.wait()
        p.expect(self.prompt)
        p.sendline('sta1 ping -c1 sta2')
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdMesh(self):
        """Start mn-wifi with wireless mesh, then test ping"""
        p = pexpect.spawn('python -m apns.examples.mesh')
        sleep(12)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdAdhoc(self):
        """Start mn-wifi with wireless adhoc, then test ping"""
        p = pexpect.spawn('python -m apns.examples.adhoc')
        sleep(10)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('sta2 ping -c1 sta3')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('sta1 ping -c1 sta3')
        p.expect('1 packets transmitted, 0 received')
        p.expect(self.prompt)
        p.sendline('sta1 ping6 -c1 2001::2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('sta2 ping6 -c1 2001::3')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('sta1 ping6 -c1 2001::3')
        p.expect('1 packets transmitted, 0 received')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('python -m apns.examples.adhoc -a')
        sleep(8)
        p.sendline('py sta1.wintfs[0].range')
        p.expect('100')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdBgscan(self):
        """Start mn-wifi, then test bgscan"""
        p = pexpect.spawn('python -m apns.examples.handover_bgscan -p')
        sleep(10)
        p.sendline('sta1 iw dev sta1-wlan0 link | grep Connected')
        p.expect('00:00:00:00:00:01')
        p.expect(self.prompt)
        p.sendline('py sta1.setPosition(\'80,40,0\')')
        sleep(15)
        p.sendline('sta1 iw dev sta1-wlan0 link | grep Connected')
        p.expect('00:00:00:00:00:02')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumd4addr(self):
        """Start mn-wifi with 4addr, then test connectivity"""
        pexpect.spawn(
            'service network-manager stop')
        p = pexpect.spawn('python -m apns.examples.4address -p')
        sleep(8)
        p.sendline('sta1 ping -c 1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdMeshAP(self):
        """Start mn-wifi, then test wifiMeshAP.py"""
        p = pexpect.spawn('python -m apns.examples.meshAP')
        sleep(12)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.wait()
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdInterference(self):
        """Start mn-wifi using wmediumd with interference, then test ping"""
        p = pexpect.spawn(
            'python -m apns.examples.wmediumd_interference -p')
        sleep(12)
        p.sendline('sta1 ping -c1 sta2')
        p.expect('1 packets transmitted, 1 received')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()

    def testWmediumdWirelessParams(self):
        """Start mn-wifi with sta in ap mode,
        then do an extensive test"""
        p = pexpect.spawn('python -m apns.examples.sta_ap_mode -p')
        sleep(12)
        p.sendline('sta1 iw dev sta1-wlan0 link | grep Connected')
        p.expect('02:00:00:00:01:00')
        p.expect(self.prompt)
        p.sendline('sta2 iw dev sta2-wlan0 link | grep Connected')
        p.expect('02:00:00:00:02:00')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].associatedTo')
        p.expect('master ap1-wlan0')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].apsInRange')
        p.expect('Station ap1: ap1-wlan0:192.168.0.10')
        p.expect(self.prompt)
        p.sendline('py sta2.wintfs[0].associatedTo')
        p.expect('master ap2-wlan0')
        p.expect(self.prompt)
        p.sendline('py sta2.wintfs[0].apsInRange')
        p.expect('Station ap2: ap2-wlan0:192.168.1.10')
        p.expect(self.prompt)
        p.sendline('net')
        p.expect('ap1 ap1-wlan0:  ap1-eth1:ap2-eth1')
        p.expect(self.prompt)
        stations = ['sta1-wlan0', self.prompt]
        p.sendline('py ap1.wintfs[0].associatedStations')
        p.expect(stations)
        p.sendline('py ap1.wintfs[0].stationsInRange')
        p.expect(stations)
        stations = ['sta2-wlan0', self.prompt]
        p.sendline('py ap2.wintfs[0].associatedStations')
        p.expect(stations)
        p.sendline('py ap2.wintfs[0].stationsInRange')
        p.expect(stations)
        p.sendline('py sta1.setPosition(\'100,40,0\')')
        sleep(5)
        p.sendline('py sta1.wintfs[0].associatedTo')
        p.expect('master ap2-wlan0')
        p.expect(self.prompt)
        p.sendline('py sta1.wintfs[0].apsInRange')
        p.expect('Station ap2: ap2-wlan0:192.168.1.10')
        p.expect(self.prompt)
        stations = ['sta1-wlan0', 'sta2-wlan0', self.prompt]
        p.sendline('py ap2.wintfs[0].associatedStations')
        p.expect(stations)
        p.sendline('py ap2.wintfs[0].stationsInRange')
        p.expect(stations)
        stations = [self.prompt]
        p.sendline('py ap1.wintfs[0].associatedStations')
        p.expect(stations)
        p.sendline('py ap1.wintfs[0].stationsInRange')
        p.expect(stations)
        p.sendline('sta1 ping -c 1 sta2')
        p.expect('0% packet loss')
        p.expect(self.prompt)
        p.sendline('py sta1.setTxPower(10, intf=\'sta1-wlan0\'')
        p.sendline('py sta1.wintfs[0].txpower')
        p.expect('10')
        p.expect(self.prompt)
        p.sendline('py sta1.setAntennaGain(10, intf=\'sta1-wlan0\'')
        p.sendline('py sta1.wintfs[0].antennaGain')
        p.expect('10')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()
        p = pexpect.spawn('python -m apns.examples.sta_ap_mode -m -p')
        p.expect(self.prompt)
        p.sendline('exit')
        p.wait()


if __name__ == '__main__':
    unittest.main()
