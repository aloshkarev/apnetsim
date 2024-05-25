import ipaddress
import os
import random
import re
import select
import shlex
import signal
import socket
from itertools import chain, groupby
from math import ceil
from subprocess import Popen
from sys import exit
from threading import Thread as thread
from time import sleep

from numpy.compat import unicode
from six import string_types

from apns.clean import Cleanup
from apns.cli import CLI
from apns.docker import Docker, DockerAP, DockerSta, DockerWLC
from apns.energy import Energy
from apns.link import (Link, TCLink, TCULink, Intf, IntfWireless, wmediumd,
                             _4address, WirelessLink, \
                             TCWirelessLink, ITSLink, WifiDirectLink, adhoc, mesh, master, managed,
                             physicalMesh, PhysicalWifiDirectLink, \
                             _4addrClient, _4addrAP, phyAP)
from apns.log import info, error, debug, output, warn
from apns.mobility import Tracked as TrackedMob, model as MobModel, \
    Mobility as mob, ConfigMobility, ConfigMobLinks
from apns.module import WifiEmu
from apns.node import (Node, Controller, OVSBridge, Host, OVSKernelSwitch,
                             OVSAP, AP, Station, physicalAP,
                             HostWLC, OVSSwitch)
from apns.nodelib import NAT
from apns.plot import Plot2D, Plot3D, PlotGraph
from apns.propagationModels import PropagationModel as ppm
from apns.telemetry import parseData, telemetry as run_telemetry
from apns.term import cleanUpScreens, makeTerms
from apns.util import (quietRun, fixLimits, macColonHex,
                             ipStr, ipParse, ipAdd,
                             waitListening, BaseString, numCores, netParse)
from apns.wmediumdConnector import error_prob, interference


class Wmnet(object):

    def __init__(self, topo=None, switch=OVSKernelSwitch, host=Host,
                 controller=Controller, intf=Intf,
                 build=True, xterms=False, cleanup=False, ipBase='10.0.0.0/8',
                 inNamespace=False, autoSetMacs=True, autoStaticArp=False,
                 autoPinCpus=False, listenPort=None, waitConnected=False,
                 accessPoint=OVSAP, station=Station, wlc=HostWLC,
                 link=wmediumd, mode="g", passwd="", ssid="default-ssid",
                 encrypt="",
                 ieee80211w=None, bridge_with=None, channel=1, freq=2.4, band=20,
                 wmediumd_mode=interference, fading_cof=0, autoAssociation=True,
                 allAutoAssociation=True, autoSetPositions=False,
                 configWiFiDirect=False, config4addr=False, noise_th=-91,
                 cca_th=-90, disable_tcp_checksum=False, ifb=False,
                 client_isolation=False, plot=False, plot3d=False, docker=False,
                 container='mn', ssh_user='admin', rec_rssi=False, start_ap_id=1,
                 json_file=None, ac_method=None, **kwargs):
        """Create Wmnet object.
           topo: Topo (topology) object or None
           switch: default Switch class
           host: default Host class/constructor
           controller: default Controller class/constructor
           link: default Link class/constructor
           intf: default Intf class/constructor
           ipBase: base IP address for hosts,
           build: build now from topo?
           xterms: if build now, spawn xterms?
           cleanup: if build now, cleanup before creating?
           inNamespace: spawn switches and controller in net namespaces?
           autoSetMacs: set MAC addrs automatically like IP addresses?
           autoStaticArp: set all-pairs static MAC addrs?
           autoPinCpus: pin hosts to (real) cores (requires CPULimitedHost)?
           listenPort: base listening port to open; will be incremented for
               each additional switch in the net if inNamespace=False
           waitConnected: wait for switches to Connect?
               (False; True/None=wait indefinitely; time(s)=timed wait)
           accessPoint: default Access Point class
           station: default Station class/constructor
           car: default Car class/constructor
           sensor: default Sensor class/constructor
           apsensor: default AP Sensor class/constructor
           link: default Link class/constructor
           ieee80211w: enable ieee80211w
           ssid: wifi ssid
           mode: wifi mode
           encrypt: wifi encrypt protocol
           passwd: passphrase
           channel: wifi channel
           freq: wifi freq
           band: bandwidth channel
           wmediumd_mode: default wmediumd mode
           fading_cof: fadding coefficient
           autoSetPositions: auto set positions
           configWiFiDirect: configure wifi direct
           config4addr: configure 4 address
           noise_th: noise threshold
           cca_th: cca threshold
           ifb: Intermediate Functional Block
           client_isolation: enables client isolation
           plot: plot graph
           plot3d: plot3d graph
           iot_module: default iot module
           wwan_module: default wwan module
           rec_rssi: sends rssi to aprf_drv by using aprf_ctrl
           json_file: json file dir
           ac_method: association control method"""
        self.topo = topo
        self.switch = switch
        self.host = host
        self.controller = controller
        self.link = link
        self.intf = intf
        self.ipBase = ipBase
        self.ipBaseNum, self.prefixLen = netParse(self.ipBase)

        hostIP = (0xffffffff >> self.prefixLen) & self.ipBaseNum
        # Start for address allocation

        self.inNamespace = inNamespace
        self.xterms = xterms
        self.cleanup = cleanup
        self.autoSetMacs = autoSetMacs
        self.autoStaticArp = autoStaticArp
        self.autoPinCpus = autoPinCpus
        self.numCores = numCores()
        self.nextCore = 0  # next core for pinning hosts to CPUs
        self.listenPort = listenPort
        self.waitConn = waitConnected

        self.SAPswitches = {}
        self.station = station
        self.accessPoint = accessPoint
        self.wlc = wlc
        self.nextPos_sta = 1  # start for sta position allocation
        self.nextPos_ap = 1  # start for ap position allocation
        self.next_sta = 1
        self.next_ap = start_ap_id
        self.nextIP = start_ap_id*10 if start_ap_id > 1 else 1
        self.autoSetPositions = autoSetPositions
        self.ssid = ssid
        self.mode = mode
        self.encrypt = encrypt
        self.passwd = passwd
        self.ieee80211w = ieee80211w
        self.ap_wlans = 2
        self.channel = channel
        self.freq = freq
        self.band = band
        self.wmediumd_mode = wmediumd_mode
        self.aps = []
        self.stations = []
        self.phones = []
        self.hosts = []
        self.switches = []
        self.controllers = []
        self.wlcs = []
        self.links = []
        self.autoAssociation = autoAssociation  # does not include mobility
        self.allAutoAssociation = allAutoAssociation  # includes mobility
        self.draw = False
        self.isReplaying = False
        self.reverse = False
        self.alt_module = None
        self.board_module = None
        self.mob_check = False
        self.mob_model = None
        self.ac_method = ac_method
        self.docker = docker
        self.container = container
        self.ssh_user = ssh_user
        self.ifb = ifb  # Support to Intermediate Functional Block (IFB) Devices
        self.json_file = json_file
        self.client_isolation = client_isolation
        self.init_plot = plot
        self.init_Plot3D = plot3d
        self.cca_th = cca_th
        self.configWiFiDirect = configWiFiDirect
        self.config4addr = config4addr
        self.fading_cof = fading_cof
        self.noise_th = noise_th
        self.disable_tcp_checksum = disable_tcp_checksum
        self.plot = Plot2D
        self.rec_rssi = rec_rssi
        self.ifbIntf = 0
        self.mob_start_time = 0
        self.mob_stop_time = 0
        self.mob_rep = 1
        self.seed = 1
        self.min_v = 1
        self.max_v = 10
        self.min_x = 0
        self.min_y = 0
        self.min_z = 0
        self.max_x = 100
        self.max_y = 100
        self.max_z = 0
        self.min_wt = 1
        self.max_wt = 5
        self.n_groups = 1
        self.wlinks = []
        self.pointlist = []
        self.initial_mediums = []
        self.nameToNode = {}  # name to Node (Host/Switch) objects
        self.bridge_with = bridge_with
        self.terms = []  # list of spawned xterm processes

        if autoSetPositions and link == wmediumd:
            self.wmediumd_mode = interference

        if not allAutoAssociation:
            self.autoAssociation = False
            mob.allAutoAssociation = False

        # we need this for scenarios where there is no mobility
        if self.ac_method:
            mob.ac = self.ac_method
        Wmnet.init()
        self.built = False
        if topo and build:
            self.build()

        Popen(shlex.split('modprobe mac80211'))
        Popen(shlex.split('modprobe aprf_drv radios=0'))

        p = Popen(shlex.split("ovs-vsctl emer-reset"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl add-br ovs-br0"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl set Interface ovs-br0 other_config:pause-flood=false"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl set Interface ovs-br0 other_config:pause-details=false"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl set Open_vSwitch . other_config:hw-offload=true"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl set Open_vSwitch . other_config:n-revalidator-threads=2"))
        p.wait()
        p = Popen(shlex.split("ovs-vsctl set Open_vSwitch . other_config:n-handler-threads=2"))
        p.wait()
        os.system("ip addr add 192.168.1.251/24 dev ovs-br0")
        os.system("ip link set ovs-br0 up")
        if self.bridge_with:
            Popen(shlex.split("ovs-vsctl add-port ovs-br0 {}".format(self.bridge_with)))

        self.setPropagationModel()
        self.runWmediumd()

    def addHost(self, name, cls=None, **params):
        """Add host.
           name: name of host to add
           cls: custom host class/constructor (optional)
           params: parameters for host
           returns: added host"""
        # Default IP and MAC addresses
        defaults = {'ip': ipAdd(self.nextIP,
                                ipBaseNum=self.ipBaseNum,
                                prefixLen=self.prefixLen) +
                          '/%s' % self.prefixLen}
        if self.autoSetMacs:
            defaults['mac'] = macColonHex(self.nextIP)
        if self.autoPinCpus:
            defaults['cores'] = self.nextCore
            self.nextCore = (self.nextCore + 1) % self.numCores
        self.nextIP += 1
        defaults.update(params)
        if not cls:
            cls = self.host
        h = cls(name, **defaults)
        self.hosts.append(h)
        self.nameToNode[name] = h
        return h

    def delHost(self, host):
        """Delete a host"""
        self.delNode(host, nodes=self.hosts)

    def addSwitch(self, name, cls=None, **params):
        """Add switch.
           name: name of switch to add
           cls: custom switch class/constructor (optional)
           returns: added switch
           side effect: increments listenPort ivar ."""
        defaults = {'listenPort': self.listenPort,
                    'inNamespace': self.inNamespace}
        defaults.update(params)
        if not cls:
            cls = self.switch
        sw = cls(name, **defaults)
        if not self.inNamespace and self.listenPort:
            self.listenPort += 1
        self.switches.append(sw)
        self.nameToNode[name] = sw
        return sw

    def addWLC(self, name, cls=None, **params):
        """Add wlc.
                   name: name of wlc to add
                   cls: custom wlc class/constructor (optional)
                   returns: added wlc
                   side effect: increments listenPort ivar ."""
        defaults = {'listenPort': self.listenPort,
                    'ip': ipAdd(self.nextIP,
                                ipBaseNum=self.ipBaseNum,
                                prefixLen=self.prefixLen) +
                          '/%s' % self.prefixLen,
                    'inNamespace': self.inNamespace}
        self.nextIP += 1
        defaults.update(params)
        if not cls:
            cls = self.wlc
        wc = cls(name, **defaults)
        if not self.inNamespace and self.listenPort:
            self.listenPort += 1
        self.wlcs.append(wc)
        self.nameToNode[name] = wc
        return wc

    def delWLC(self, wlc):
        self.delNode(wlc, nodes=self.wlcs)

    def delSwitch(self, switch):
        """Delete a switch"""
        self.delNode(switch, nodes=self.switches)

    def addController(self, name='c0', controller=None, **params):
        """Add controller.
           controller: Controller class"""
        # Get controller class
        if not controller:
            controller = self.controller
        # Construct new controller if one is not given
        if isinstance(name, Controller):
            controller_new = name
            # Pylint thinks controller is a str()
            # pylint: disable=maybe-no-member
            name = controller_new.name
            # pylint: enable=maybe-no-member
        else:
            controller_new = controller(name, **params)
        # Add new controller to net
        if controller_new:  # allow controller-less setups
            self.controllers.append(controller_new)
            self.nameToNode[name] = controller_new
        return controller_new

    def delController(self, controller):
        """Delete a controller
           Warning - does not reconfigure switches, so they
           may still attempt to connect to it!"""
        self.delNode(controller)

    # BL: We now have four ways to look up nodes
    # This may (should?) be cleaned up in the future.
    def getNodeByName(self, *args):
        """Return node(s) with given name(s)"""
        if len(args) == 1:
            return self.nameToNode[args[0]]
        return [self.nameToNode[n] for n in args]

    def configureControlNetwork(self):
        """Control net config hook: override in subclass"""
        raise Exception('configureControlNetwork: '
                        'should be overriden in subclass', self)

    def stopXterms(self):
        """Kill each xterm."""
        for term in self.terms:
            os.kill(term.pid, signal.SIGKILL)
        cleanUpScreens()

    def runCpuLimitTest(self, cpu, duration=5):
        """run CPU limit test with 'while true' processes.
        cpu: desired CPU fraction of each host
        duration: test duration in seconds (integer)
        returns a single list of measured CPU fractions as floats.
        """
        pct = cpu * 100
        info('--- Testing CPU %.0f%% bandwidth limit\n' % pct)
        hosts = self.hosts
        cores = int(quietRun('nproc'))
        # number of processes to run a while loop on per host
        num_procs = int(ceil(cores * cpu))
        pids = {}
        for h in hosts:
            pids[h] = []
            for _core in range(num_procs):
                h.cmd('while true; do a=1; done &')
                pids[h].append(h.cmd('echo $!').strip())
        outputs = {}
        time = {}
        # get the initial cpu time for each host
        for host in hosts:
            outputs[host] = []
            with open('/sys/fs/cgroup/cpuacct/%s/cpuacct.usage' %
                      host, 'r') as f:
                time[host] = float(f.read())
        for _ in range(duration):
            sleep(1)
            for host in hosts:
                with open('/sys/fs/cgroup/cpuacct/%s/cpuacct.usage' %
                          host, 'r') as f:
                    readTime = float(f.read())
                outputs[host].append(((readTime - time[host])
                                      / 1000000000) / cores * 100)
                time[host] = readTime
        for h, pids in pids.items():
            for pid in pids:
                h.cmd('kill -9 %s' % pid)
        cpu_fractions = []
        for _host, outputs in outputs.items():
            for pct in outputs:
                cpu_fractions.append(pct)
        output('--- Results: %s\n' % cpu_fractions)
        return cpu_fractions

    @classmethod
    def init(cls):
        """Initialize Wmnet"""
        if cls.inited:
            return
        fixLimits()
        cls.inited = True

    def getNextIp(self):
        ip = ipAdd(self.nextIP,
                   ipBaseNum=self.ipBaseNum,
                   prefixLen=self.prefixLen) + '/%s' % self.prefixLen
        self.nextIP += 1
        return ip

    def removeHost(self, name, **kwargs):
        """
        Remove a host from the network at runtime.
        """
        if not isinstance(name, BaseString) and name is not None:
            name = name.name  # if we get a host object
        try:
            n = self.get(name)
        except:
            error("Host: %s not found. Cannot remove it.\n" % name)
            return False
        if n is not None:
            if n in self.hosts:
                self.hosts.remove(n)
            if n in self.stations:
                self.stations.remove(n)
            if name in self.nameToNode:
                del self.nameToNode[name]
            n.stop(deleteIntfs=True)
            debug("Removed: %s\n" % name)
            return True
        return False

    def socketServer(self, **kwargs):
        thread(target=self.start_socket, kwargs=kwargs).start()

    def start_socket(self, ip='127.0.0.1', port=12345):
        Cleanup.socket_port = port

        if ':' in ip:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((ip, port))
        s.listen(1)

        while True:
            conn, addr = s.accept()
            try:
                thread(target=self.get_socket_data, args=(conn, addr)).start()
            except:
                info("Thread did not start.\n")

    def get_socket_data(self, conn, addr):
        while True:
            try:
                cmd = conn.recv(1024).decode('utf-8')
                pos = None
                if 'setPosition' in cmd:
                    pos = cmd.split('("')[1].split(')"')[0][:-2]
                data = cmd.split('.')
                if data[0] == 'set':
                    node = self.getNodeByName(data[1])
                    if len(data) < 3:
                        data = 'usage: set.node.method()'
                    else:
                        if data[2] == 'sumo':
                            mod = __import__('apns.sumo.function', fromlist=[data[3]])
                            method_to_call = getattr(mod, data[3])
                            node = self.getNodeByName(data[1])
                            node.sumo = method_to_call
                            node.sumoargs = str(data[4])
                            data = 'command accepted!'
                        else:
                            attr = data[2].split('(')
                            if hasattr(node, attr[0]):
                                method_to_call = getattr(node, attr[0])
                                if 'intf' in attr[1]:
                                    val = attr[1].split(', intf=')
                                    intf = val[1][:-1]
                                    val = val[0]
                                    method_to_call(val, intf=intf)
                                else:
                                    val = pos if pos else attr[1].split(')')[0]
                                    method_to_call(val.replace('"', '').replace("'", ""))
                                    data = 'command accepted!'
                            else:
                                data = 'unrecognized method!'
                elif data[0] == 'get':
                    node = self.getNodeByName(data[1])
                    if len(data) < 3:
                        data = 'usage: get.node.attr'
                    else:
                        if 'wintfs' in data[2]:
                            i = int(data[2][7:-1])
                            wintfs = getattr(node, 'wintfs')[i]
                            data = getattr(wintfs, data[3])
                        else:
                            data = getattr(node, data[2])
                else:
                    try:
                        cmd = ''
                        for d in range(1, len(data)):
                            cmd = cmd + data[d] + ' '
                        node = self.getNodeByName(data[0])
                        node.pexec(cmd)
                        data = 'command accepted!'
                    except:
                        data = 'unrecognized option {}:'.format(data[0])
                conn.send(str(data).encode('utf-8'))
                break
            except:
                conn.close()

    def waitConnected(self, timeout=None, delay=.5):
        """wait for each switch to connect to a controller,
           up to 5 seconds
           timeout: time to wait, or None to wait indefinitely
           delay: seconds to sleep per iteration
           returns: True if all switches are connected"""
        info('--- Waiting for switches/aps to connect\n')
        time = 0
        L2nodes = self.switches + self.aps
        remaining = list(L2nodes)
        while True:
            for switch in tuple(remaining):
                if switch.connected():
                    info(switch)
                    remaining.remove(switch)
            if not remaining:
                info('\n')
                return True
            if timeout is not None and time > timeout:
                break
            sleep(delay)
            time += delay
        warn('Timed out after {} seconds\n'.format(time))
        for switch in remaining:
            if not switch.connected():
                warn('Warning: {} is not connected '
                     'to a controller\n'.format(switch.name))
            else:
                remaining.remove(switch)
        return not remaining

    def pos_to_array(self, node):
        pos = node.params['position']
        if isinstance(pos, string_types):
            pos = pos.split(',')
        node.position = [float(pos[0]), float(pos[1]), float(pos[2])]
        node.params.pop('position', None)

    def count_ifaces(self):
        """Count the number of virtual wifi interfaces"""
        nodes = self.stations + self.aps
        nradios = 0
        for node in nodes:
            nradios += len(node.params['wlan'])
        return nodes, nradios

    def config_runtime_node(self, node):
        self.configNode(node)
        node.wmIfaces = []
        for intf in node.wintfs.values():
            intf.ipLink('up')
            if isinstance(node, AP):
                self.configMasterIntf(node, intf.id)
                intf.configureMacAddr()
                node.wintfs[intf.id].mac = intf.mac
            else:
                intf.configureMacAddr()
                intf.setIP(intf.ip, intf.prefixLen)
            if self.link == wmediumd:
                intf.sendIntfTowmediumd()
            if self.draw or hasattr(node, 'position'):
                intf.setTxPower(intf.txpower)
                intf.setAntennaGain(intf.antennaGain)
                intf.node.lastpos = 0, 0, 0
                if self.draw:
                    self.plot.instantiate_attrs(node)

    def addWlans(self, node):
        node.params['wlan'] = []
        wlans = node.params.get('wlans', 1)
        for wlan in range(wlans):
            wlan_id = wlan
            node.params['wlan'].append('wlan' + str(wlan_id))
        node.params.pop("wlans", None)
        WifiEmu(node=node, on_the_fly=True)
        self.config_runtime_node(node)

    def addSta(self, cls=DockerSta, amount=1, **params):
        """Add Station.
           name: name of station to add
           cls: custom host class/constructor (optional)
           params: parameters for station
           returns: added station"""
        # Default IP and MAC addresses
        sta_array = []
        for i in range(amount):
            defaults = {'ip': ipAdd(self.nextIP,
                                    ipBaseNum=self.ipBaseNum,
                                    prefixLen=self.prefixLen) +
                              '/{}'.format(self.prefixLen),
                        # 'ip6': ipAdd6(self.nextIP6,
                        #               ipBaseNum=self.ip6BaseNum,
                        #               prefixLen=self.prefixLen6) +
                        #        '/{}'.format(self.prefixLen6),
                        'channel': self.channel,
                        'band': self.band,
                        'freq': self.freq,
                        'mode': self.mode,
                        'encrypt': self.encrypt,
                        'passwd': self.passwd,
                        'ieee80211w': self.ieee80211w
                        }
            defaults.update(params)
            name = "sta" + str(self.next_sta)
            debug("\naddSta: ++++++++++ %s ++++++++++\n" % name)
            self.next_sta += 1

            if self.autoSetPositions and 'position' not in params:
                defaults['position'] = [round(self.nextPos_sta, 2), 0, 0]
            if self.autoPinCpus:
                defaults['cores'] = self.nextCore
                self.nextCore = (self.nextCore + 1) % self.numCores
            self.nextIP += 1
            self.nextPos_sta += 2

            if not cls:
                cls = self.station
            sta = cls(name, **defaults)

            if 'position' in params or self.autoSetPositions:
                self.pos_to_array(sta)

            self.addWlans(sta)
            self.stations.append(sta)
            self.nameToNode[name] = sta
            debug("\n addSta: ---------- /%s ----------\n" % name)
            sta_array.append(sta)
        return sta_array

    def delSta(self, station):
        """del Station.
           name: name of station to remove
           returns: result"""
        self.delNode(station, nodes=self.stations)

    def addAP(self, cls=DockerAP, amount=1, **params):
        """Add AccessPoint.
           name: name of accesspoint to add
           cls: custom switch class/constructor (optional)
           returns: added accesspoint
           side effect: increments listenPort var ."""
        ap_array = []
        for i in range(amount):
            defaults = {'listenPort': self.listenPort,
                        'inNamespace': self.inNamespace,
                        'ssid': self.ssid,
                        'channel': self.channel,
                        'band': self.band,
                        'freq': self.freq,
                        'mode': self.mode,
                        'encrypt': self.encrypt,
                        'passwd': self.passwd,
                        'ieee80211w': self.ieee80211w,
                        'wlans': self.ap_wlans
                        }
            name = "ap" + str(self.next_ap)
            info("%s " % name )
            debug("\n++++++++++ %s ++++++++++\n" % name)
            self.nextIP = self.next_ap*20 - 19
            self.next_ap += 1
            if self.client_isolation:
                defaults['client_isolation'] = True
            if self.json_file:
                defaults['json'] = self.json_file
            defaults.update(params)
            if self.autoSetPositions:
                defaults['position'] = [round(self.nextPos_ap, 2), 50, 0]
                self.nextPos_ap += 1
            wlan = None
            if cls and isinstance(cls, physicalAP):
                wlan = params.pop('phywlan', {})
                cls = self.accessPoint
            if not cls:
                cls = self.accessPoint
            ap = cls(name, **defaults)
            if not self.inNamespace and self.listenPort:
                self.listenPort += 1
            self.nameToNode[name] = ap
            if wlan:
                ap.params['phywlan'] = wlan
            if 'position' in params or self.autoSetPositions:
                self.pos_to_array(ap)
            self.addWlans(ap)
            self.aps.append(ap)
            debug("\n--------- /%s ----------\n" % name)
            ap_array.append(ap)
            info("")
        return ap_array

    def delAP(self, ap):
        """del AccessPoint.
           name: name of accesspoint to remove
           returns: result"""
        self.delNode(ap, nodes=self.aps)

    def setStaticRoute(self, node, ip=None, **params):
        """Set the static route to go through intf.
           net: subnet address"""
        # Note setParam won't call us if intf is none
        if isinstance(ip, BaseString) and ' ' in ip:
            params = ip
        else:
            natIP = ip.split('/')[0]
            params = '{} via {}'.format(params['net'], natIP)
        # Do this in one line in case we're messing with the root namespace
        node.cmd('ip route add', params)

    def addNAT(self, name='nat0', connect=True, inNamespace=False,
               linkTo=None, **params):
        """Add a NAT to the Wmnet network
           name: name of NAT node
           connect: switch to connect to | True (s1) | None
           inNamespace: create in a network namespace
           params: other NAT node params, notably:
               ip: used as default gateway address"""
        nat = self.addHost(name, cls=NAT, inNamespace=inNamespace,
                           subnet=self.ipBase, **params)
        # find first ap and create link
        if connect:
            if not isinstance(connect, Node):
                if linkTo:
                    nodes = self.switches + self.aps + self.wlcs
                    for node in nodes:
                        if linkTo == node.name:
                            connect = node
                else:
                    if self.switches:
                        connect = self.switches[0]
                    elif self.aps:
                        connect = self.aps[0]
            # Connect the nat to the ap
            self.addLink(nat, connect)
            # Set the default route on stations
            natIP = nat.params['ip'].split('/')[0]
            nodes = self.stations + self.hosts
            if 'net' in params:
                for node in nodes:
                    if node.inNamespace:
                        self.setStaticRoute(node, '{} via {}'.format(params['net'], natIP))
            else:
                for node in nodes:
                    if node.inNamespace:
                        node.setDefaultRoute('via {}'.format(natIP))
        return nat

    def __iter__(self):
        """return iterator over node names"""
        for node in chain(self.hosts, self.switches, self.controllers,
                          self.stations, self.aps, self.wlcs,
                          self.phones):
            yield node.name

    def __len__(self):
        """returns number of nodes in net"""
        return (len(self.hosts) + len(self.switches) +
                len(self.controllers) + len(self.stations) +
                len(self.aps) + len(self.wlcs) + (self.phones))

    def setModule(self, moduleDir):
        """set an alternative module rather than aprf_drv"""
        self.alt_module = moduleDir

    def do_association(self, intf, ap_intf):
        dist = intf.node.get_distance_to(ap_intf.node)
        if dist > ap_intf.range:
            return False
        return True

    def get_intf(self, node1, node2, port1=None, port2=None):
        wlan1, wlan2 = 0, 0

        if node1 in self.stations and node2 in self.stations:
            n1 = node1
            n2 = node2
        else:
            n1 = node1 if node2 in self.aps else node2
            n2 = node1 if node1 in self.aps else node2

            if port1 is not None and port2 is not None:
                wlan1 = port1 if node2 in self.aps else port2
                wlan2 = port1 if node1 in self.aps else port2

        intf1 = n1.wintfs[wlan1]
        intf2 = n2.wintfs[wlan2]

        return intf1, intf2

    def infra_wmediumd_link(self, node1, node2, port1=None, port2=None,
                            **params):
        intf1, intf2 = self.get_intf(node1, node2, port1, port2)

        if 'error_prob' not in params:
            intf1.associate(intf2)

        if self.wmediumd_mode == error_prob:
            self.wlinks.append([intf1, intf2, params['error_prob']])
        elif self.wmediumd_mode != interference:
            self.wlinks.append([intf1, intf2])

    def infra_tc(self, node1, node2, port1=None, port2=None,
                 cls=None, **params):
        intf, ap_intf = self.get_intf(node1, node2, port1, port2)
        do_association = True
        if hasattr(intf.node, 'position') and hasattr(ap_intf.node, 'position'):
            do_association = self.do_association(intf, ap_intf)
        if do_association:
            if 'bw' not in params and 'bw' not in str(cls):
                params['bw'] = intf.getCustomRate() if hasattr(intf.node, 'position') else intf.getCustomRate()
            # tc = True, this is useful for tc configuration
            TCWirelessLink(node=intf.node, intfName=intf.name,
                           port=intf.id, cls=cls, **params)
            intf.associate(ap_intf)

    def addLink(self, node1, node2=None, port1=None, port2=None,
                cls=None, **params):
        """"Add a link from node1 to node2
            node1: source node (or name)
            node2: dest node (or name)
            port1: source port (optional)
            port2: dest port (optional)
            cls: link class (optional)
            params: additional link params (optional)
            returns: link object"""

        # Accept node objects or names
        node1 = node1 if not isinstance(node1, string_types) else self[node1]
        node2 = node2 if not isinstance(node2, string_types) else self[node2]
        options = dict(params)

        cls = self.link if cls is None else cls

        modes = [mesh, adhoc, ITSLink, WifiDirectLink, PhysicalWifiDirectLink]
        if cls in modes:
            link = cls(node=node1, **params)
            self.links.append(link)
            if node2 and self.wmediumd_mode == error_prob:
                self.infra_wmediumd_link(node1, node2, **params)
            return link
        elif cls == physicalMesh:
            cls(node=node1, **params)
        elif cls == _4address:
            if self.wmediumd_mode == interference:
                link = cls(node1, node2, port1, port2, **params)
                self.links.append(link)
                return link

            if self.do_association(node1.wintfs[0], node2.wintfs[0]):
                link = cls(node1, node2, **params)
                self.links.append(link)
                return link
        elif ((node1 in self.stations and node2 in self.aps)
              or (node2 in self.stations and node1 in self.aps)) and cls != TCLink:
            if cls == wmediumd:
                self.infra_wmediumd_link(node1, node2, **params)
            else:
                self.infra_tc(node1, node2, port1, port2, cls, **params)
        else:
            if not cls or cls == wmediumd or cls == WirelessLink:
                cls = TCLink
            if self.disable_tcp_checksum:
                cls = TCULink
            if 'link' in options:
                options.pop('link', None)

            # Port is optional
            if port1 is not None:
                options.setdefault('port1', port1)
            if port2 is not None:
                options.setdefault('port2', port2)

            # Set default MAC - this should probably be in Link
            options.setdefault('addr1', self.randMac())
            options.setdefault('addr2', self.randMac())

            if not cls or cls == wmediumd or cls == WirelessLink:
                cls = TCLink
            if self.disable_tcp_checksum:
                cls = TCULink

            cls = self.link if cls is None else cls
            link = cls(node1, node2, **options)

            # Allow to add links at runtime
            # (needs attach method provided by OVSSwitch)
            if isinstance(node1, OVSSwitch) or isinstance(node1, AP):
                node1.attach(link.intf1)
            if isinstance(node2, OVSSwitch) or isinstance(node2, AP):
                node2.attach(link.intf2)

            self.links.append(link)
            return link

    def delNode(self, node, nodes=None):
        """Delete node
           node: node to delete
           nodes: optional list to delete from (e.g. self.hosts)"""
        if nodes is None:
            nodes = (self.hosts if node in self.hosts else
                     (self.stations if node in self.stations else
                      (self.aps if node in self.aps else
                       (self.switches if node in self.switches else
                        (self.controllers if node in self.controllers else
                         (self.wlcs if node in self.wlcs else
                          []))))))
        node.stop(deleteIntfs=True)
        node.terminate()
        nodes.remove(node)
        del self.nameToNode[node.name]

    def get(self, *args):
        """Convenience alias for getNodeByName"""
        return self.getNodeByName(*args)

    # Even more convenient syntax for node lookup and iteration
    def __getitem__(self, key):
        """net[ name ] operator: Return node with given name"""
        return self.nameToNode[key]

    def __delitem__(self, key):
        """del net[ name ] operator - delete node with given name"""
        self.delNode(self.nameToNode[key])

    def __contains__(self, item):
        """returns True if net contains named node"""
        return item in self.nameToNode

    def keys(self):
        """return a list of all node names or net's keys"""
        return list(self)

    def values(self):
        """return a list of all nodes or net's values"""
        return [self[name] for name in self]

    def items(self):
        """return (key,value) tuple list for every node in net"""
        return zip(self.keys(), self.values())

    @staticmethod
    def randMac():
        """Return a random, non-multicast MAC address"""
        return macColonHex(random.randint(1, 2 ** 48 - 1) & 0xfeffffffffff |
                           0x020000000000)

    def removeLink(self, link=None, node1=None, node2=None):
        """
        Removes a link. Can either be specified by link object,
        or the nodes the link connects.
        """
        if link is None:
            if (isinstance(node1, BaseString)
                    and isinstance(node2, BaseString)):
                try:
                    node1 = self.get(node1)
                except:
                    error("Host: %s not found.\n" % node1)
                try:
                    node2 = self.get(node2)
                except:
                    error("Host: %s not found.\n" % node2)
            # try to find link by nodes
            for l in self.links:
                if l.intf1.node == node1 and l.intf2.node == node2:
                    link = l
                    break
                if l.intf1.node == node2 and l.intf2.node == node1:
                    link = l
                    break
        if link is None:
            error("Couldn't find link to be removed.\n")
            return
        # tear down the link
        link.delete()
        self.links.remove(link)

    def delLink(self, link):
        """Remove a link from this network"""
        link.delete()
        self.links.remove(link)

    def linksBetween(self, node1, node2):
        """Return Links between node1 and node2"""
        return [link for link in self.links
                if (node1, node2) in (
                    (link.intf1.node, link.intf2.node),
                    (link.intf2.node, link.intf1.node))]

    def delLinkBetween(self, node1, node2, index=0, allLinks=False):
        """Delete link(s) between node1 and node2
           index: index of link to delete if multiple links (0)
           allLinks: ignore index and delete all such links (False)
           returns: deleted link(s)"""
        links = self.linksBetween(node1, node2)
        if not allLinks:
            links = [links[index]]
        for link in links:
            self.delLink(link)
        return links

    def stop(self):
        self.stop_graph_params()
        # info('--- Removing NAT rules of %i SAPs\n' % len(self.SAPswitches))
        # for SAPswitch in self.SAPswitches:
        #     self.removeSAPNAT(self.SAPswitches[SAPswitch])
        # info("\n")
        "Stop the controller(s), switches and hosts"
        info('--- Stop SDN controllers (%i)\n' % len(self.controllers))
        for controller in self.controllers:
            info(controller.name + ' ')
            controller.stop()
        info('\n')
        if self.terms:
            info('--- Close terminals (%i)\n' % len(self.terms))
            self.stopXterms()
        info('--- Close links (%i)\n' % len(self.links))
        for link in self.links:
            info('.')
            link.stop()
        info('\n')
        nodesL2 = self.switches + self.aps + self.wlcs
        info('--- Stop network elements (%i)\n' % len(nodesL2))
        stopped = {}
        for swclass, switches in groupby(
                sorted(self.switches,
                       key=lambda s: str(type(s))), type):
            switches = tuple(switches)
            if hasattr(swclass, 'batchShutdown'):
                success = swclass.batchShutdown(switches)
                stopped.update({s: s for s in success})
        for switch in nodesL2:
            info(switch.name + ' ')
            if switch not in stopped:
                switch.stop()
            switch.terminate()
        info('\n')
        nodes = self.hosts + self.stations + self.phones
        info('--- Stop nodes (%i)\n' % len(nodes))
        for node in nodes:
            info(node.name + ' ')
            node.terminate()
        self.close_apns()
        info('\n--- Done\n')

    def run(self, test, *args, **kwargs):
        """Perform a complete start/test/stop cycle."""
        self.start()
        info('--- Run test\n')
        result = test(*args, **kwargs)
        self.stop()
        return result

    def monitor(self, hosts=None, timeoutms=-1):
        """Monitor a set of hosts (or all hosts by default),
           and return their output, a line at a time.
           hosts: (optional) set of hosts to monitor
           timeoutms: (optional) timeout value in ms
           returns: iterator which returns host, line"""
        if hosts is None:
            hosts = self.hosts
        poller = select.poll()
        h1 = hosts[0]  # so we can call class method fdToNode
        for host in hosts:
            poller.register(host.stdout)
        while True:
            ready = poller.poll(timeoutms)
            for fd, event in ready:
                host = h1.fdToNode(fd)
                if event & select.POLLIN:
                    line = host.readline()
                    if line is not None:
                        yield host, line
            # Return if non-blocking
            if not ready and timeoutms >= 0:
                yield None, None

    def configHosts(self):
        """Configure a set of nodes."""
        nodes = self.hosts
        for node in nodes:
            # info( host.name + ' ' )
            intf = node.defaultIntf()
            if intf:
                node.configDefault()
            else:
                # Don't configure nonexistent intf
                node.configDefault(ip=None, mac=None)
                # You're low priority, dude!
                # BL: do we want to do this here or not?
                # May not make sense if we have CPU lmiting...
                # quietRun( 'renice +18 -p ' + repr( host.pid ) )
                # This may not be the right place to do this, but
                # it needs to be done somewhere.
        info('\n')

    def buildFromWirelessTopo(self, topo=None):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""
        info('--- Add Stations:\n')
        for staName in topo.stations():
            self.addSta(staName, **topo.nodeInfo(staName))
            info(staName + ' ')

        info('\n--- Add APs:\n')
        for apName in topo.aps():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo(apName)
            cls = params.get('cls', self.accessPoint)
            if hasattr(cls, 'batchStartup'):
                params.setdefault('batch', True)
            self.addAP(apName, **params)
            info(apName + ' ')

        info('\n--- Add WLC:\n')
        for wlcName in topo.wlcs():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo(wlcName)
            cls = params.get('cls', self.wlc)
            if hasattr(cls, 'batchStartup'):
                params.setdefault('batch', True)
            self.addWLC(wlcName, **params)
            info(wlcName + ' ')

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info('--- Network\n')

        if not self.controllers and self.controller:
            # Add a default controller
            info('--- SDN controller\n')
            classes = self.controller
            if not isinstance(classes, list):
                classes = [classes]
            for i, cls in enumerate(classes):
                # Allow Controller objects because nobody understands partial()
                if isinstance(cls, Controller):
                    self.addController(cls)
                else:
                    self.addController('c%d' % i, cls)

        info('--- Hosts:\n')
        for hostName in topo.hosts():
            self.addHost(hostName, **topo.nodeInfo(hostName))
            info(hostName + ' ')

        info('\n--- Switches:\n')
        for switchName in topo.switches():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo(switchName)
            cls = params.get('cls', self.switch)
            # if hasattr( cls, 'batchStartup' ):
            #    params.setdefault( 'batch', True )
            self.addSwitch(switchName, **params)
            info(switchName + ' ')

        info('\n--- Links:\n')
        for srcName, dstName, params in topo.links(
                sort=True, withInfo=True):
            self.addLink(**params)
            info('(%s, %s) ' % (srcName, dstName))

        info('\n')

    def check_if_mob(self):
        if self.mob_model or self.mob_stop_time:
            mob_params = self.get_mobility_params()
            stat_nodes, mob_nodes = self.get_mob_stat_nodes()
            method = TrackedMob
            if self.mob_model:
                method = self.start_mobility
            method(stat_nodes=stat_nodes, mob_nodes=mob_nodes, **mob_params)
            self.mob_check = True
        else:
            if self.draw and not self.isReplaying:
                self.check_dimension(self.get_apns_nodes())

    def staticArp(self):
        """Add all-pairs ARP entries to remove the need to handle broadcast."""
        nodes = self.stations + self.hosts
        for src in nodes:
            for dst in nodes:
                if src != dst:
                    src.setARP(ip=dst.IP(), mac=dst.MAC())

    def hasVoltageParam(self):
        nodes = self.get_apns_nodes()
        energy_nodes = []
        for node in nodes:
            if 'voltage' in node.params:
                energy_nodes.append(node)
        if energy_nodes:
            Energy(energy_nodes)

    def build(self):
        """Build mininet-wifi."""
        if self.topo:
            self.buildFromWirelessTopo(self.topo)
            if self.init_plot or self.init_Plot3D:
                max_z = 0
                if self.init_Plot3D:
                    max_z = len(self.stations) * 100
                self.plotGraph(max_x=(len(self.stations) * 100),
                               max_y=(len(self.stations) * 100),
                               max_z=max_z)
        else:
            if not mob.stations:
                for node in self.stations:
                    if hasattr(node, 'position'):
                        mob.stations.append(node)

        if self.config4addr or self.configWiFiDirect or self.wmediumd_mode == error_prob:
            # sync with the current 2nd interface type
            for id, link in enumerate(self.wlinks):
                for node in self.stations:
                    for intf in node.wintfs.values():
                        if intf.name == link[1].name:
                            self.wlinks[id][1] = intf
            self.init_wmediumd()

        if self.inNamespace:
            self.configureControlNetwork()

        debug('--- Configuration\n')
        self.configHosts()
        if self.xterms:
            self.startTerms()
        if self.autoStaticArp:
            self.staticArp()

        if not self.mob_check:
            self.check_if_mob()

        if self.allAutoAssociation:
            if self.autoAssociation and not self.configWiFiDirect:
                self.auto_association()

        self.hasVoltageParam()
        self.built = True

    def startTerms(self):
        """Start a terminal for each node."""
        if 'DISPLAY' not in os.environ:
            error("Error starting terms: Cannot connect to display\n")
            return
        info("--- Running terms on %s\n" % os.environ['DISPLAY'])
        cleanUpScreens()
        self.terms += makeTerms(self.controllers, 'controller')
        self.terms += makeTerms(self.switches, 'switch')
        self.terms += makeTerms(self.hosts, 'host')
        self.terms += makeTerms(self.stations, 'station')
        self.terms += makeTerms(self.aps, 'ap')
        self.terms += makeTerms(self.wlcs, 'wlc')
        self.terms += makeTerms(self.phones, 'phone')

    def telemetry(self, **kwargs):
        run_telemetry(**kwargs)

    def start(self):
        """Start controller and switches."""

        if not self.built:
            self.build()

        if not self.mob_check:
            self.check_if_mob()

        info('--- SDN Controllers\n')
        for controller in self.controllers:
            info(controller.name + ' ')
            controller.start()
        info('\n')

        info('--- L2 Elements\n')
        nodesL2 = self.switches + self.aps + self.wlcs
        for nodeL2 in nodesL2:
            info(nodeL2.name + ' ')
            if not isinstance(nodeL2, DockerAP) and not isinstance(nodeL2, DockerWLC):
                nodeL2.start(self.controllers)

        started = {}
        for swclass, switches in groupby(
                sorted(nodesL2, key=lambda x: str(type(x))), type):
            switches = tuple(switches)
            if hasattr(swclass, 'batchStartup'):
                success = swclass.batchStartup(switches)
                started.update({s: s for s in success})
        info('\n')
        if self.waitConn:
            self.waitConnected()

    @staticmethod
    def _parsePing(pingOutput):
        """Parse ping output and return packets sent, received."""
        # Check for downed link
        if 'connect: Network is unreachable' in pingOutput:
            return 1, 0
        r = r'(\d+) packets transmitted, (\d+)( packets)? received'
        m = re.search(r, pingOutput)
        if m is None:
            error('--- Error: could not parse ping output: %s\n' %
                  pingOutput)
            return 1, 0
        sent, received = int(m.group(1)), int(m.group(2))
        return sent, received

    def ping(self, hosts=None, timeout=None, manualdestip=None):
        """Ping between all specified hosts.
           hosts: list of hosts
           timeout: time to wait for a response, as string
           manualdestip: sends pings from each h in hosts to manualdestip
           returns: ploss packet loss percentage"""
        # should we check if running?
        packets = 0
        lost = 0
        ploss = None

        if not hosts:
            hosts = self.hosts + self.stations
            output('--- Ping: testing ping reachability\n')
        for node in hosts:
            output('%s -> ' % node.name)
            if manualdestip is not None:
                opts = ''
                if timeout:
                    opts = '-W %s' % timeout
                result = node.cmd('ping -c1 %s %s' %
                                  (opts, manualdestip))
                sent, received = self._parsePing(result)
                packets += sent
                if received > sent:
                    error('--- Error: received too many packets')
                    error('%s' % result)
                    node.cmdPrint('route')
                    exit(1)
                lost += sent - received
                output(('%s ' % manualdestip) if received else 'X ')
            else:
                for dest in hosts:
                    if node != dest:
                        opts = ''
                        if timeout:
                            opts = '-W %s' % timeout
                        if dest.intfs:
                            result = node.cmd('ping -c1 %s %s' %
                                              (opts, dest.IP()))
                            sent, received = self._parsePing(result)
                        else:
                            sent, received = 0, 0
                        packets += sent
                        if received > sent:
                            error('--- Error: received too many packets')
                            error('%s' % result)
                            node.cmdPrint('route')
                            exit(1)
                        lost += sent - received
                        output(('%s ' % dest.name) if received else 'X ')
            output('\n')
        if packets > 0:
            ploss = 100.0 * lost / packets
            received = packets - lost
            output("--- Results: %i%% dropped (%d/%d received)\n" %
                   (ploss, received, packets))
        else:
            ploss = 0
            output("--- Warning: No packets sent\n")
        return ploss

    @staticmethod
    def _parsePingFull(pingOutput):
        """Parse ping output and return all data."""
        errorTuple = (1, 0, 0, 0, 0, 0)
        # Check for downed link
        r = r'[uU]nreachable'
        m = re.search(r, pingOutput)
        if m is not None:
            return errorTuple
        r = r'(\d+) packets transmitted, (\d+)( packets)? received'
        m = re.search(r, pingOutput)
        if m is None:
            error('--- Error: could not parse ping output: %s\n' %
                  pingOutput)
            return errorTuple
        sent, received = int(m.group(1)), int(m.group(2))
        r = r'rtt min/avg/max/mdev = '
        r += r'(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'
        m = re.search(r, pingOutput)
        if m is None:
            if received == 0:
                return errorTuple
            error('--- Error: could not parse ping output: %s\n' %
                  pingOutput)
            return errorTuple
        rttmin = float(m.group(1))
        rttavg = float(m.group(2))
        rttmax = float(m.group(3))
        rttdev = float(m.group(4))
        return sent, received, rttmin, rttavg, rttmax, rttdev

    def pingFull(self, hosts=None, timeout=None, manualdestip=None):
        """Ping between all specified hosts and return all data.
           hosts: list of hosts
           timeout: time to wait for a response, as string
           returns: all ping data; see function body."""
        # should we check if running?
        # Each value is a tuple: (src, dsd, [all ping outputs])
        all_outputs = []
        if not hosts:
            hosts = self.hosts
            output('--- Ping: testing ping reachability\n')
        for node in hosts:
            output('%s -> ' % node.name)
            if manualdestip is not None:
                opts = ''
                if timeout:
                    opts = '-W %s' % timeout
                result = node.cmd('ping -c1 %s %s' % (opts, manualdestip))
                outputs = self._parsePingFull(result)
                sent, received, rttmin, rttavg, rttmax, rttdev = outputs
                all_outputs.append((node, manualdestip, outputs))
                output(('%s ' % manualdestip) if received else 'X ')
                output('\n')
            else:
                for dest in hosts:
                    if node != dest:
                        opts = ''
                        if timeout:
                            opts = '-W %s' % timeout
                        result = node.cmd('ping -c1 %s %s' % (opts, dest.IP()))
                        outputs = self._parsePingFull(result)
                        sent, received, rttmin, rttavg, rttmax, rttdev = outputs
                        all_outputs.append((node, dest, outputs))
                        output(('%s ' % dest.name) if received else 'X ')
        output("--- Results: \n")
        for outputs in all_outputs:
            src, dest, ping_outputs = outputs
            sent, received, rttmin, rttavg, rttmax, rttdev = ping_outputs
            output(" %s->%s: %s/%s, " % (src, dest, sent, received))
            output("rtt min/avg/max/mdev %0.3f/%0.3f/%0.3f/%0.3f ms\n" %
                   (rttmin, rttavg, rttmax, rttdev))
        return all_outputs

    def pingAll(self, timeout=None):
        """Ping between all hosts.
           returns: ploss packet loss percentage"""
        return self.ping(timeout=timeout)

    def pingPair(self):
        """Ping between first two hosts, useful for testing.
           returns: ploss packet loss percentage"""
        nodes = self.hosts + self.stations
        hosts = [nodes[0], nodes[1]]
        return self.ping(hosts=hosts)

    def pingAllFull(self):
        """Ping between all hosts.
           returns: ploss packet loss percentage"""
        return self.pingFull()

    def pingPairFull(self):
        """Ping between first two hosts, useful for testing.
           returns: ploss packet loss percentage"""
        nodes = self.hosts + self.stations
        hosts = [nodes[0], nodes[1]]
        return self.pingFull(hosts=hosts)

    @staticmethod
    def _parseIperf(iperfOutput):
        """Parse iperf output and return bandwidth.
           iperfOutput: string
           returns: result string"""
        r = r'([\d\.]+ \w+/sec)'
        m = re.findall(r, iperfOutput)
        if m:
            return m[-1]
        else:
            # was: raise Exception(...)
            error('could not parse iperf output: ' + iperfOutput)
            return ''

    def iperf(self, hosts=None, l4Type='TCP', udpBw='10M', fmt=None,
              seconds=5, port=5001):
        """Run iperf between two hosts.
           hosts: list of hosts; if None, uses first and last hosts
           l4Type: string, one of [ TCP, UDP ]
           udpBw: bandwidth target for UDP test
           fmt: iperf format argument if any
           seconds: iperf time to transmit
           port: iperf port
           returns: two-element array of [ server, client ] speeds
           note: send() is buffered, so client rate can be much higher than
           the actual transmission rate; on an unloaded system, server
           rate should be much closer to the actual receive rate"""
        sleep(3)
        nodes = self.hosts + self.stations
        hosts = hosts or [nodes[0], nodes[-1]]
        assert len(hosts) == 2
        client, server = hosts

        conn1 = 0
        conn2 = 0
        if isinstance(client, Station) or isinstance(server, Station):
            cmd = 'iw dev {} link | grep -ic \'Connected\''
            if isinstance(client, Station):
                while conn1 == 0:
                    conn1 = int(client.cmd(cmd.format(client.wintfs[0].name)))
            if isinstance(server, Station):
                while conn2 == 0:
                    conn2 = int(server.cmd(cmd.format(server.wintfs[0].name)))
        output('--- Iperf: testing', l4Type, 'bandwidth between',
               client, 'and', server, '\n')
        server.cmd('killall -9 iperf3')
        iperfArgs = 'iperf3 -p %d ' % port
        bwArgs = ''
        if l4Type == 'UDP':
            iperfArgs += '-u '
            bwArgs = '-b ' + udpBw + ' '
        elif l4Type != 'TCP':
            raise Exception('Unexpected l4 type: {}'.format(l4Type))
        if fmt:
            iperfArgs += '-f {} '.format(fmt)

        server.sendCmd(iperfArgs + '-s')
        if l4Type == 'TCP':
            if not waitListening(client, server.IP(), port):
                raise Exception('Could not connect to iperf on port %d'
                                % port)
        cliout = client.cmd(iperfArgs + '-t %d -c ' % seconds +
                            server.IP() + ' ' + bwArgs)
        debug('Client output: {}\n'.format(cliout))
        servout = ''
        # We want the last *b/sec from the iperf server output
        # for TCP, there are two of them because of waitListening
        count = 2 if l4Type == 'TCP' else 1
        while len(re.findall('/sec', servout)) < count:
            debug('Server output: {}\n'.format(servout))
            servout += server.monitor(timeoutms=5000)

        server.sendInt()
        servout += server.waitOutput()
        debug('Server output: {}\n'.format(servout))
        result = [self._parseIperf(servout), self._parseIperf(cliout)]
        if l4Type == 'UDP':
            result.insert(0, udpBw)
        output('--- Results: {}\n'.format(result))
        return result

    def get_apns_nodes(self):
        return self.stations + self.aps + self.phones

    def get_distance(self, src, dst):
        """
        gets the distance between two nodes
        :params src: source node
        :params dst: destination node
        """
        nodes = self.get_apns_nodes()
        try:
            src = self.nameToNode[src]
            if src in nodes:
                dst = self.nameToNode[dst]
                if dst in nodes:
                    dist = src.get_distance_to(dst)
                    info("The distance between {} and "
                         "{} is {} meters\n".format(src, dst, dist))
        except KeyError:
            info("node {} or/and node {} does not exist or "
                 "there is no position defined\n".format(dst, src))

    def mobility(self, *args, **kwargs):
        """Configure mobility parameters"""
        ConfigMobility(*args, **kwargs)

    def get_mob_stat_nodes(self):
        mob_nodes = []
        stat_nodes = []
        nodes = self.stations + self.aps
        for node in nodes:
            if hasattr(node, 'position') and 'initPos' not in node.params:
                stat_nodes.append(node)
            else:
                mob_nodes.append(node)
        return stat_nodes, mob_nodes

    def setPropagationModel(self, **kwargs):
        ppm.set_attr(self.noise_th, self.cca_th, **kwargs)

    def setInitialMediums(self, mediums):
        self.initial_mediums = mediums

    def configNodesStatus(self, src, dst, status):
        sta = self.nameToNode[dst]
        ap = self.nameToNode[src]
        if isinstance(self.nameToNode[src], Station):
            sta = self.nameToNode[src]
            ap = self.nameToNode[dst]

        if status == 'down':
            for intf in sta.wintfs.values():
                if intf.associatedTo:
                    intf.disconnect(ap.wintfs[0])
        else:
            for intf in sta.wintfs.values():
                if not intf.associatedTo:
                    intf.iw_connect(ap.wintfs[0])

    # BL: I think this can be rewritten now that we have
    # a real link class.
    def configLinkStatus(self, src, dst, status):
        """Change status of src <-> dst links.
           src: node name
           dst: node name
           status: string {up, down}"""
        if src not in self.nameToNode:
            error('src not in network: {}\n'.format(src))
        elif dst not in self.nameToNode:
            error('dst not in network: {}\n'.format(dst))

        condition1 = [isinstance(self.nameToNode[src], Station),
                      isinstance(self.nameToNode[dst], AP)]
        condition2 = [isinstance(self.nameToNode[src], AP),
                      isinstance(self.nameToNode[dst], Station)]

        if all(condition1) or all(condition2):
            self.configNodesStatus(src, dst, status)
        else:
            src = self.nameToNode[src]
            dst = self.nameToNode[dst]
            connections = src.connectionsTo(dst)
            if len(connections) == 0:
                error('src and dst not connected: {} {}\n'.format(src, dst))
            for srcIntf, dstIntf in connections:
                result = srcIntf.ifconfig(status)
                if result:
                    error('link src status change failed: {}\n'.format(result))
                result = dstIntf.ifconfig(status)
                if result:
                    error('link dst status change failed: {}\n'.format(result))

    def interact(self):
        """Start network and run our simple CLI."""
        self.start()
        result = CLI(self)
        self.stop()
        return result

    inited = False

    def createVirtualIfaces(self, nodes):
        """Creates virtual wifi interfaces"""
        for node in nodes:
            if 'nvif' in node.params:
                debug("Virtual Interfaces call \n")
                for vif_ in range(node.params['nvif']):
                    vif = node.params['wlan'][0] + str(vif_ + 1)
                    node.params['wlan'].append(vif)
                    mac = str(node.wintfs[0].mac)
                    new_mac = '{}{}{}'.format(mac[:4], vif_ + 1, mac[5:])
                    node.cmd('iw dev {} interface add {} '
                             'type station'.format(node.params['wlan'][0], vif))
                    TCWirelessLink(node, intfName=vif)
                    managed(node, wlan=vif_ + 1)

                    node.wintfs[vif_ + 1].mac = new_mac
                    for intf in node.wintfs.values():
                        intf.configureMacAddr()

    def configIFB(self, node):
        for wlan in range(1, len(node.params['wlan'])):
            if self.ifb:
                node.configIFB(wlan, self.ifbIntf)  # Adding Support to IFB
                node.wintfs[wlan - 1].ifb = 'ifb' + str(wlan)
                self.ifbIntf += 1

    def configNode(self, node):
        """Configure Wireless Link"""
        for wlan in range(len(node.params['wlan'])):
            if not self.autoAssociation:
                intf = node.params['wlan'][wlan]
                link = TCWirelessLink(node, intfName=intf)
                self.links.append(link)
            managed(node, wlan)
        for intf in node.wintfs.values():
            if self.autoSetMacs:
                intf.mac = macColonHex(self.nextIP)
                self.nextIP += 9
            intf.configureMacAddr()
        node.configDefault()

    def plotGraph(self, **kwargs):
        """Plots Graph"""
        self.draw = True
        for key, value in kwargs.items():
            setattr(self, key, value)
        if kwargs.get('max_z', 0) != 0:
            self.plot = Plot3D
        Cleanup.plot = self.plot

    def check_dimension(self, nodes):
        try:
            for node in nodes:
                if hasattr(node, 'coord'):
                    node.position = node.coord[0].split(',')
            PlotGraph(min_x=self.min_x, min_y=self.min_y, min_z=self.min_z,
                      max_x=self.max_x, max_y=self.max_y, max_z=self.max_z,
                      nodes=nodes, links=self.links)
            if not issubclass(self.plot, Plot3D):
                PlotGraph.pause()
        except:
            info('Something went wrong with the GUI.\n')
            self.draw = False

    def start_mobility(self, **kwargs):
        """Starts Mobility"""
        for node in kwargs.get('mob_nodes'):
            node.position, node.pos = (0, 0, 0), (0, 0, 0)
        MobModel(**kwargs)

    def setMobilityModel(self, **kwargs):
        for key in kwargs:
            if key == 'model':
                self.mob_model = kwargs.get(key)
            elif key == 'time':
                self.mob_start_time = kwargs.get(key)
            elif key in self.__dict__.keys():
                setattr(self, key, kwargs.get(key))

    def startMobility(self, **kwargs):
        for key in kwargs:
            if key == 'time':
                self.mob_start_time = kwargs.get(key)
            else:
                setattr(self, key, kwargs.get(key))

    def stopMobility(self, **kwargs):
        """Stops Mobility"""
        if self.allAutoAssociation and \
                not self.configWiFiDirect and not self.config4addr:
            self.auto_association()
        for key in kwargs:
            if key == 'time':
                self.mob_stop_time = kwargs.get(key)
            else:
                setattr(self, key, kwargs.get(key))

    def get_mobility_params(self):
        """Set Mobility Parameters"""
        mob_params = {}
        float_args = ['min_x', 'min_y', 'min_z',
                      'max_x', 'max_y', 'max_z',
                      'min_v', 'max_v', 'min_wt', 'max_wt']
        args = ['stations', 'aps', 'draw', 'seed',
                'mob_start_time', 'mob_stop_time',
                'links', 'mob_model', 'mob_rep', 'reverse',
                'ac_method', 'pointlist', 'n_groups']
        args += float_args
        for arg in args:
            if arg in float_args:
                mob_params.setdefault(arg, float(getattr(self, arg)))
            else:
                mob_params.setdefault(arg, getattr(self, arg))

        mob_params.setdefault('ppm', ppm.model)
        return mob_params

    def start_wmediumd(self):
        wmediumd(wlinks=self.wlinks, fading_cof=self.fading_cof,
                 noise_th=self.noise_th, stations=self.stations,
                 aps=self.aps, ppm=ppm, mediums=self.initial_mediums)

    def run_wmediumd(self):
        wmediumd(fading_cof=self.fading_cof,
                 noise_th=self.noise_th,
                 ppm=ppm)

    def init_wmediumd(self):
        self.start_wmediumd()
        if self.wmediumd_mode != error_prob:
            for sta in self.stations:
                sta.set_pos_wmediumd(sta.position)
        for sta in self.stations:
            if sta in self.aps:
                self.stations.remove(sta)
        self.config_antenna()

    def config_range(self):
        nodes = self.stations + self.aps
        for node in nodes:
            for intf in node.wintfs.values():
                if int(intf.range) == 0:
                    intf.setDefaultRange()
                else:
                    # assign txpower according to the signal range
                    if 'model' not in node.params:
                        intf.getTxPowerGivenRange()

    def config_antenna(self):
        nodes = self.stations + self.aps
        for node in nodes:
            for intf in node.wintfs.values():
                if not isinstance(intf, (_4addrAP, PhysicalWifiDirectLink, phyAP)):
                    intf.setTxPower(intf.txpower)
                    intf.setAntennaGain(intf.antennaGain)

    def configMasterIntf(self, node, wlan):
        TCWirelessLink(node, port=wlan)
        master(node, wlan, port=wlan)
        phy = node.params.get('phywlan', None)
        if phy:
            TCWirelessLink(node, intfName=phy)
            node.params['wlan'].append(phy)
            phyAP(node, wlan)

    def runWmediumd(self):
        """Run Wmediumd"""
        if self.link == wmediumd:
            self.wmediumd_mode()
            if not self.configWiFiDirect and not self.config4addr \
                    and self.wmediumd_mode != error_prob:
                self.run_wmediumd()

    def configureWmediumd(self):
        """Configure WiFi Nodes"""
        params = {}

        if self.docker:
            params['docker'] = self.docker
            params['container'] = self.container
            params['ssh_user'] = self.ssh_user
        params['rec_rssi'] = self.rec_rssi

        if self.link == wmediumd:
            self.wmediumd_mode()
            if not self.configWiFiDirect and not self.config4addr \
                    and self.wmediumd_mode != error_prob:
                self.start_wmediumd()

    @staticmethod
    def wmediumd_workaround(node, value=0):
        # We need to set the position after starting wmediumd
        sleep(0.15)
        pos = node.position
        pos_x = float(pos[0]) + value
        pos = (pos_x, pos[1], pos[2])
        node.set_pos_wmediumd(pos)

    def restore_links(self):
        # restore link params when it is manually set
        for link in self.links:
            params = {}
            if 'bw' in link.intf1.params:
                params['bw'] = link.intf1.params['bw']
            if 'latency' in link.intf1.params:
                params['latency'] = link.intf1.params['latency']
            if 'loss' in link.intf1.params:
                params['loss'] = link.intf1.params['loss']
            if params and 'delay' not in link.intf1.params and hasattr(link.intf1, 'configWLink'):
                link.intf1.configWLink.set_tc(link.intf1.name, **params)

    def auto_association(self):
        """This is useful to make the users' life easier"""
        isap = []

        for node in self.stations:
            for intf in node.wintfs.values():
                if isinstance(intf, master) or \
                        isinstance(intf, _4addrClient or isinstance(intf, _4addrAP)):
                    if node not in self.aps and node not in isap:
                        isap.append(node)

        for sta in isap:
            self.aps.append(sta)
            self.stations.remove(sta)
            if sta in mob.stations:
                mob.stations.remove(sta)

        mob.aps = self.aps
        nodes = self.aps + self.stations
        for node in nodes:
            if hasattr(node, 'position'):
                for intf in node.wintfs.values():
                    if isinstance(intf, adhoc):
                        info(node.name + ' ')
                        sleep(1)
                node.pos = (0, 0, 0)
                if not isinstance(node, AP):
                    ConfigMobLinks(node)
                # we need this cause wmediumd is struggling
                # with some associations e.g. wpa
                if self.wmediumd_mode == interference:
                    self.wmediumd_workaround(node)
                    self.wmediumd_workaround(node, -1)

        self.restore_links()

        nodes = self.stations
        for node in nodes:
            for wlan in range(len(node.params['wlan'])):
                intf = node.params['wlan'][wlan]
                link = TCWirelessLink(node, intfName=intf, port=wlan)
                self.links.append(link)
                # lets set ip/mac to intfs
                node.intfs[wlan].ip = node.wintfs[wlan].ip
                node.intfs[wlan].mac = node.wintfs[wlan].mac

    @staticmethod
    def stop_simulation():
        """Pause the simulation"""
        mob.pause_simulation = True

    @staticmethod
    def start_simulation():
        """Start the simulation"""
        mob.pause_simulation = False

    @staticmethod
    def setChannelEquation(**params):
        """Set Channel Equation
        :params bw: bandwidth (mbps)
        :params delay: delay (ms)
        :params latency: latency (ms)
        :params loss: loss (%)"""
        IntfWireless.eqBw = params.get('bw', IntfWireless.eqBw)
        IntfWireless.eqDelay = params.get('delay', IntfWireless.eqDelay)
        IntfWireless.eqLatency = params.get('latency', IntfWireless.eqLatency)
        IntfWireless.eqLoss = params.get('loss', IntfWireless.eqLoss)

    @staticmethod
    def stop_graph_params():
        """Stop the graph"""
        if parseData.thread_:
            parseData.thread_._keep_alive = False
        if mob.thread_:
            mob.thread_._keep_alive = False
        if Energy.thread_:
            Energy.thread_._keep_alive = False
            sleep(1)
        sleep(0.5)

    @classmethod
    def close_apns(self):
        """Close MN-WiFi"""
        Cleanup.cleanup()

    def addDocker(self, name, cls=Docker, **params):
        """
        Wrapper for addHost method that adds a
        Docker container as a host.
        """
        return self.addHost(name, cls=cls, **params)

    def removeDocker(self, name, **params):
        """
        Wrapper for removeHost. Just to be complete.
        """
        return self.removeHost(name, **params)

    def addExtSAP(self, sapName, sapIP, dpid=None, **params):
        """
        Add an external Service Access Point, implemented as an OVSBridge
        :param sapName:
        :param sapIP: str format: x.x.x.x/x
        :param dpid:
        :param params:
        :return:
        """
        SAPswitch = self.addSwitch(sapName, cls=OVSBridge, prefix='sap.',
                                   dpid=dpid, ip=sapIP, **params)
        self.SAPswitches[sapName] = SAPswitch

        NAT = params.get('NAT', False)
        if NAT:
            self.addSAPNAT(SAPswitch)

        return SAPswitch

    def removeExtSAP(self, sapName):
        SAPswitch = self.SAPswitches[sapName]
        info('stopping external SAP:' + SAPswitch.name + ' \n')
        SAPswitch.stop()
        SAPswitch.terminate()

        self.removeSAPNAT(SAPswitch)

    def addSAPNAT(self, SAPSwitch, SAPNet):
        """
        Add NAT to the Containernet, so external SAPs can reach the outside internet through the host
        :param SAPSwitch: Instance of the external SAP switch
        :param SAPNet: Subnet of the external SAP as str (eg. '10.10.1.0/30')
        :return:
        """
        SAPip = SAPSwitch.ip
        SAPNet = str(ipaddress.IPv4Network(unicode(SAPip), strict=False))
        # due to a bug with python-iptables, removing and finding rules does not succeed when the mininet CLI is running
        # so we use the iptables tool
        # create NAT rule
        rule0_ = "iptables -t nat -A POSTROUTING ! -o {0} -s {1} -j MASQUERADE".format(SAPSwitch.deployed_name, SAPNet)
        p = Popen(shlex.split(rule0_))
        p.communicate()

        # create FORWARD rule
        rule1_ = "iptables -A FORWARD -o {0} -j ACCEPT".format(SAPSwitch.deployed_name)
        p = Popen(shlex.split(rule1_))
        p.communicate()

        rule2_ = "iptables -A FORWARD -i {0} -j ACCEPT".format(SAPSwitch.deployed_name)
        p = Popen(shlex.split(rule2_))
        p.communicate()

        info("added SAP NAT rules for: {0} - {1}\n".format(SAPSwitch.name, SAPNet))

    def removeSAPNAT(self, SAPSwitch):
        SAPip = SAPSwitch.ip
        SAPNet = str(ipaddress.IPv4Network(unicode(SAPip), strict=False))
        # due to a bug with python-iptables, removing and finding rules does not succeed when the mininet CLI is running
        # so we use the iptables tool
        rule0_ = "iptables -t nat -D POSTROUTING ! -o {0} -s {1} -j MASQUERADE".format(SAPSwitch.deployed_name, SAPNet)
        p = Popen(shlex.split(rule0_))
        p.communicate()

        rule1_ = "iptables -D FORWARD -o {0} -j ACCEPT".format(SAPSwitch.deployed_name)
        p = Popen(shlex.split(rule1_))
        p.communicate()

        rule2_ = "iptables -D FORWARD -i {0} -j ACCEPT".format(SAPSwitch.deployed_name)
        p = Popen(shlex.split(rule2_))
        p.communicate()

        info("remove SAP NAT rules for: {0} - {1}\n".format(SAPSwitch.name, SAPNet))


class WmnetWithControlWNet(Wmnet):
    """Control network support:
       Create an explicit control network. Currently this is only
       used/usable with the user datapath.
       Notes:
       1. If the controller and switches are in the same (e.g. root)
          namespace, they can just use the loopback connection.
       2. If we can get unix domain sockets to work, we can use them
          instead of an explicit control network.
       3. Instead of routing, we could bridge or use 'in-band' control.
       4. Even if we dispense with this in general, it could still be
          useful for people who wish to simulate a separate control
          network (since real networks may need one!)
       5. Basically nobody ever used this code, so it has been moved
          into its own class.
       6. Ultimately we may wish to extend this to allow us to create a
          control network which every node's control interface is
          attached to."""

    def configureControlNetwork(self):
        """Configure control network."""
        self.configureRoutedControlNetwork()

    # We still need to figure out the right way to pass
    # in the control network location.

    def configureRoutedControlNetwork(self, ip='192.168.123.1',
                                      prefixLen=16):
        """Configure a routed control network on controller and switches.
           For use with the user datapath only right now."""
        controller = self.controllers[0]
        info(controller.name + ' <->')
        cip = ip
        snum = ipParse(ip)
        nodesL2 = self.switches + self.aps
        for nodeL2 in nodesL2:
            info(' ' + nodeL2.name)
            if self.link == wmediumd:
                link = Link(nodeL2, controller, port1=0)
            else:
                self.link = Link
                link = self.link(nodeL2, controller, port1=0)
            sintf, cintf = link.intf1, link.intf2
            nodeL2.controlIntf = sintf
            snum += 1
            while snum & 0xff in [0, 255]:
                snum += 1
            sip = ipStr(snum)
            cintf.setIP(cip, prefixLen)
            sintf.setIP(sip, prefixLen)
            controller.setHostRoute(sip, cintf)
            nodeL2.setHostRoute(cip, sintf)
        info('\n')
        info('--- Testing control network\n')
        while not cintf.isUp():
            info('--- Waiting for', cintf, 'to come up\n')
            sleep(1)
        for nodeL2 in nodesL2:
            while not sintf.isUp():
                info('--- Waiting for', sintf, 'to come up\n')
                sleep(1)
            if self.ping(hosts=[nodeL2, controller]) != 0:
                error('--- Error: control network test failed\n')
                exit(1)
        info('\n')
