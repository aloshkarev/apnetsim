#!/usr/bin/env python

"""
mn-edit: a simple network editor for MN-WiFi

This is a simple demonstration of how one might build a
GUI application using MN-WiFi as the network model.
"""

# Miniedit needs some work in order to pass pylint...
# pylint: disable=line-too-long,too-many-branches
# pylint: disable=too-many-statements,attribute-defined-outside-init
# pylint: disable=missing-docstring

MINIEDIT_VERSION = '2.3'

import json
import os
import re
import sys
from functools import partial
from optparse import OptionParser
from subprocess import call
from tkinter import (Frame, Label, LabelFrame, Entry, OptionMenu, Checkbutton,
                     Menu, Toplevel, Button, BitmapImage, PhotoImage, Canvas,
                     Scrollbar, Wm, StringVar, IntVar,
                     E, W, EW, NW, Y, VERTICAL, SOLID, CENTER, ttk,
                     messagebox, font, filedialog, simpledialog,
                     RIGHT, LEFT, BOTH, TRUE, FALSE)

from packaging.version import Version as StrictVersion

if 'PYTHONPATH' in os.environ:
    sys.path = os.environ['PYTHONPATH'].split(':') + sys.path

# someday: from ttk import *

from apns.log import info, debug, warn, setLogLevel
from apns.util import netParse, ipAdd, quietRun
from apns.util import buildTopo
from apns.util import custom, customClass
from apns.term import makeTerm, cleanUpScreens
from apns.node import Controller, RemoteController, OVSController, HostWLC, ExternalWLC
from apns.node import CPULimitedHost, Host, Node
from apns.node import OVSSwitch, UserSwitch
from apns.link import TCLink, Intf, Link
from apns.moduledeps import moduleDeps
from apns.topo import SingleSwitchTopo, LinearTopo, SingleSwitchReversedTopo
from apns.topolib import TreeTopo

from apns.cli import CLI
from apns.net import Wmnet
from apns.node import CPULimitedStation, Station, OVSAP, UserAP

from apns.link import wmediumd, master
from apns.mobility import Mobility, ConfigMobLinks
from apns.module import WifiEmu
from apns.wmediumdConnector import interference

TOPODEF = 'none'
TOPOS = {'minimal': lambda: SingleSwitchTopo(k=2),
         'linear': LinearTopo,
         'reversed': SingleSwitchReversedTopo,
         'single': SingleSwitchTopo,
         'none': None,
         'tree': TreeTopo}
CONTROLLERDEF = 'ref'
CONTROLLERS = {'ref': Controller,
               'ovsc': OVSController,
               'remote': RemoteController,
               'none': lambda name: None}
LINKDEF = 'default'
LINKS = {'default': Link,
         'tc': TCLink}
HOSTDEF = 'proc'
HOSTS = {'proc': Host,
         'rt': custom(CPULimitedHost, sched='rt'),
         'cfs': custom(CPULimitedHost, sched='cfs')}

WLCDEF = 'hwlc'
WLCS = {'hwlc': HostWLC,
        'ewlc': ExternalWLC}


class InbandController(RemoteController):
    """RemoteController that ignores checkListening"""

    def checkListening(self):
        """Overridden to do nothing."""
        return


class CustomUserSwitch(UserSwitch):
    """Customized UserSwitch"""

    def __init__(self, name, dpopts='--no-slicing', **kwargs):
        UserSwitch.__init__(self, name, **kwargs)
        self.switchIP = None

    def getSwitchIP(self):
        """Return management IP address"""
        return self.switchIP

    def setSwitchIP(self, ip):
        """Set management IP address"""
        self.switchIP = ip

    def start(self, controllers):
        """Start and set management IP address"""
        # Call superclass constructor
        UserSwitch.start(self, controllers)
        # Set Switch IP address
        if self.switchIP is not None:
            if not self.inNamespace:
                self.cmd('ifconfig', self, self.switchIP)
            else:
                self.cmd('ifconfig lo', self.switchIP)


class CustomUserAP(UserAP):
    """Customized UserAP"""

    def __init__(self, name, dpopts='--no-slicing', **kwargs):
        UserAP.__init__(self, name, **kwargs)
        self.apIP = None

    def getAPIP(self):
        """Return management IP address"""
        return self.apIP

    def setAPIP(self, ip):
        """Set management IP address"""
        self.apIP = ip

    def start(self, controllers):
        """Start and set management IP address"""
        # Call superclass constructor
        UserAP.start(self, controllers)
        # Set AP IP address
        if self.apIP is not None:
            if not self.inNamespace:
                self.cmd('ifconfig', self, self.apIP)
            else:
                self.cmd('ifconfig lo', self.apIP)


class LegacyRouter(Node):
    """Simple IP router"""

    def __init__(self, name, inNamespace=True, **params):
        Node.__init__(self, name, inNamespace, **params)

    def config(self, **_params):
        if self.intfs:
            self.setParam(_params, 'setIP', ip='0.0.0.0')
        r = Node.config(self, **_params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        return r


class LegacySwitch(OVSSwitch):
    """OVS switch in standalone/bridge mode"""

    def __init__(self, name, **params):
        OVSSwitch.__init__(self, name, failMode='standalone', **params)
        self.switchIP = None


class customOvs(OVSSwitch):
    """Customized OVS switch"""

    def __init__(self, name, failMode='secure', datapath='kernel', **params):
        OVSSwitch.__init__(self, name, failMode=failMode, datapath=datapath, **params)
        self.switchIP = None

    def getSwitchIP(self):
        """Return management IP address"""
        return self.switchIP

    def setSwitchIP(self, ip):
        """Set management IP address"""
        self.switchIP = ip

    def start(self, controllers):
        """Start and set management IP address"""
        # Call superclass constructor
        OVSSwitch.start(self, controllers)
        # Set Switch IP address
        if self.switchIP is not None:
            self.cmd('ifconfig', self, self.switchIP)


class customOvsAP(OVSAP):
    """Customized OVS switch"""

    def __init__(self, name, failMode='secure', datapath='kernel', **params):
        OVSAP.__init__(self, name, failMode=failMode, datapath=datapath, **params)
        self.apIP = None

    def getAPIP(self):
        """Return management IP address"""
        return self.apIP

    def setAPIP(self, ip):
        """Set management IP address"""
        self.apIP = ip

    def start(self, controllers):
        """Start and set management IP address"""
        # Call superclass constructor
        OVSAP.start(self, controllers)
        # Set AP IP address
        if self.apIP is not None:
            self.cmd('ifconfig', self, self.apIP)


class PrefsDialog(simpledialog.Dialog):
    """Preferences dialog"""

    def __init__(self, parent, title, prefDefaults):

        self.prefValues = prefDefaults

        simpledialog.Dialog.__init__(self, parent, title)

    def body(self, master):
        """Create dialog body"""
        self.rootFrame = master
        self.leftfieldFrame = Frame(self.rootFrame, padx=5, pady=5)
        self.leftfieldFrame.grid(row=0, column=0, sticky='nswe', columnspan=2)
        self.rightfieldFrame = Frame(self.rootFrame, padx=5, pady=5)
        self.rightfieldFrame.grid(row=0, column=2, sticky='nswe', columnspan=2)

        # Field for Base IP
        Label(self.leftfieldFrame, text="IP Base:").grid(row=0, sticky=E)
        self.ipEntry = Entry(self.leftfieldFrame)
        self.ipEntry.grid(row=0, column=1)
        ipBase = self.prefValues['ipBase']
        self.ipEntry.insert(0, ipBase)

        # Selection of terminal type
        row = 1
        Label(self.leftfieldFrame, text="Default Terminal:").grid(row=row, sticky=E)
        self.terminalVar = StringVar(self.leftfieldFrame)
        self.terminalOption = OptionMenu(self.leftfieldFrame, self.terminalVar, "xterm", "gterm")
        self.terminalOption.grid(row=row, column=1, sticky=W)
        terminalType = self.prefValues['terminalType']
        self.terminalVar.set(terminalType)

        # Field for CLI
        row += 1
        Label(self.leftfieldFrame, text="Start CLI:").grid(row=row, sticky=E)
        self.cliStart = IntVar()
        self.cliButton = Checkbutton(self.leftfieldFrame, variable=self.cliStart)
        self.cliButton.grid(row=row, column=1, sticky=W)
        if self.prefValues['startCLI'] == '0':
            self.cliButton.deselect()
        else:
            self.cliButton.select()

        # Field for Wmediumd
        row += 1
        Label(self.leftfieldFrame, text="Enable Wmediumd:").grid(row=row, sticky=E)
        self.enWmediumd = IntVar()
        self.cliButton = Checkbutton(self.leftfieldFrame, variable=self.enWmediumd)
        self.cliButton.grid(row=row, column=1, sticky=W)
        if self.prefValues['enableWmediumd'] == '0':
            self.cliButton.deselect()
        else:
            self.cliButton.select()

        # Selection of switch type
        row += 1
        Label(self.leftfieldFrame, text="Default Switch:").grid(row=row, sticky=E)
        self.switchType = StringVar(self.leftfieldFrame)
        self.switchTypeMenu = OptionMenu(self.leftfieldFrame, self.switchType, "Open vSwitch Kernel Mode",
                                         "Userspace", "Userspace inNamespace")
        self.switchTypeMenu.grid(row=row, column=1, sticky=W)
        switchTypePref = self.prefValues['switchType']
        if switchTypePref == 'userns':
            self.switchType.set("Userspace inNamespace")
        elif switchTypePref == 'user':
            self.switchType.set("Userspace")
        else:
            self.switchType.set("Open vSwitch Kernel Mode")

        # Selection of switch type
        row += 1
        Label(self.leftfieldFrame, text="Default WLC:").grid(row=row, sticky=E)
        self.wlcType = StringVar(self.leftfieldFrame)
        self.wlcTypeMenu = OptionMenu(self.leftfieldFrame, self.wlcType, "Host WLC",
                                      "External WLC")
        self.wlcTypeMenu.grid(row=row, column=1, sticky=W)
        wlcTypePref = self.prefValues['wlcType']
        if wlcTypePref == 'hwlc':
            self.wlcType.set("Host WLC")
        else:
            self.wlcType.set("External WLC")

        # Selection of ap type
        row += 1
        Label(self.leftfieldFrame, text="Default AP/Switch:").grid(row=row, sticky=E)
        self.apType = StringVar(self.leftfieldFrame)
        self.apTypeMenu = OptionMenu(self.leftfieldFrame, self.apType,
                                     "Open vSwitch Kernel Mode",
                                     "Userspace", "Userspace inNamespace")
        self.switchTypeMenu.grid(row=row, column=1, sticky=W)
        apTypePref = self.prefValues['apType']
        if apTypePref == 'userns':
            self.apType.set("Userspace inNamespace")
        elif apTypePref == 'user':
            self.apType.set("Userspace")
        else:
            self.apType.set("Open vSwitch Kernel Mode")

        # Selection of mode
        row += 1
        Label(self.leftfieldFrame, text="Mode:").grid(row=3, sticky=E)
        self.mode = StringVar(self.leftfieldFrame)
        self.modeMenu = OptionMenu(self.leftfieldFrame, self.mode, "g", "a",
                                   "b", "n")
        self.modeMenu.grid(row=3, column=1, sticky=W)
        modePref = self.prefValues['mode']
        if modePref == 'g':
            self.mode.set("g")
        elif modePref == 'a':
            self.mode.set("a")
        elif modePref == 'b':
            self.mode.set("b")
        elif modePref == 'n':
            self.mode.set("n")
        else:
            self.mode.set("g")

        # Selection of authentication type
        Label(self.leftfieldFrame, text="Authentication:").grid(row=3, sticky=E)
        self.authentication = StringVar(self.leftfieldFrame)
        self.authenticationMenu = OptionMenu(self.leftfieldFrame, self.authentication, "none", "WEP",
                                             "WPA", "WPA2", "8021x")
        self.authenticationMenu.grid(row=3, column=1, sticky=W)
        authenticationPref = self.prefValues['authentication']
        if authenticationPref == 'WEP':
            self.authentication.set("WEP")
        elif authenticationPref == 'WPA':
            self.authentication.set("WPA")
        elif authenticationPref == 'WPA2':
            self.authentication.set("WPA2")
        elif authenticationPref == '8021x':
            self.authentication.set("8021x")
        else:
            self.authentication.set("none")

        # Fields for OVS OpenFlow version
        ovsFrame = LabelFrame(self.leftfieldFrame, text='Open vSwitch', padx=5, pady=5)
        ovsFrame.grid(row=4, column=0, columnspan=2, sticky=EW)
        Label(ovsFrame, text="OpenFlow 1.0:").grid(row=0, sticky=E)
        Label(ovsFrame, text="OpenFlow 1.1:").grid(row=1, sticky=E)
        Label(ovsFrame, text="OpenFlow 1.2:").grid(row=2, sticky=E)
        Label(ovsFrame, text="OpenFlow 1.3:").grid(row=3, sticky=E)

        self.ovsOf10 = IntVar()
        self.covsOf10 = Checkbutton(ovsFrame, variable=self.ovsOf10)
        self.covsOf10.grid(row=0, column=1, sticky=W)
        if self.prefValues['openFlowVersions']['ovsOf10'] == '0':
            self.covsOf10.deselect()
        else:
            self.covsOf10.select()

        self.ovsOf11 = IntVar()
        self.covsOf11 = Checkbutton(ovsFrame, variable=self.ovsOf11)
        self.covsOf11.grid(row=1, column=1, sticky=W)
        if self.prefValues['openFlowVersions']['ovsOf11'] == '0':
            self.covsOf11.deselect()
        else:
            self.covsOf11.select()

        self.ovsOf12 = IntVar()
        self.covsOf12 = Checkbutton(ovsFrame, variable=self.ovsOf12)
        self.covsOf12.grid(row=2, column=1, sticky=W)
        if self.prefValues['openFlowVersions']['ovsOf12'] == '0':
            self.covsOf12.deselect()
        else:
            self.covsOf12.select()

        self.ovsOf13 = IntVar()
        self.covsOf13 = Checkbutton(ovsFrame, variable=self.ovsOf13)
        self.covsOf13.grid(row=3, column=1, sticky=W)
        if self.prefValues['openFlowVersions']['ovsOf13'] == '0':
            self.covsOf13.deselect()
        else:
            self.covsOf13.select()

        # Field for DPCTL listen port
        row += 1
        Label(self.leftfieldFrame, text="dpctl port:").grid(row=row, sticky=E)
        self.dpctlEntry = Entry(self.leftfieldFrame)
        self.dpctlEntry.grid(row=row, column=1)
        if 'dpctl' in self.prefValues:
            self.dpctlEntry.insert(0, self.prefValues['dpctl'])

        # sFlow
        sflowValues = self.prefValues['sflow']
        self.sflowFrame = LabelFrame(self.rightfieldFrame, text='sFlow Profile for Open vSwitch', padx=5, pady=5)
        self.sflowFrame.grid(row=0, column=0, columnspan=2, sticky=EW)

        Label(self.sflowFrame, text="Target:").grid(row=0, sticky=E)
        self.sflowTarget = Entry(self.sflowFrame)
        self.sflowTarget.grid(row=0, column=1)
        self.sflowTarget.insert(0, sflowValues['sflowTarget'])

        Label(self.sflowFrame, text="Sampling:").grid(row=1, sticky=E)
        self.sflowSampling = Entry(self.sflowFrame)
        self.sflowSampling.grid(row=1, column=1)
        self.sflowSampling.insert(0, sflowValues['sflowSampling'])

        Label(self.sflowFrame, text="Header:").grid(row=2, sticky=E)
        self.sflowHeader = Entry(self.sflowFrame)
        self.sflowHeader.grid(row=2, column=1)
        self.sflowHeader.insert(0, sflowValues['sflowHeader'])

        Label(self.sflowFrame, text="Polling:").grid(row=3, sticky=E)
        self.sflowPolling = Entry(self.sflowFrame)
        self.sflowPolling.grid(row=3, column=1)
        self.sflowPolling.insert(0, sflowValues['sflowPolling'])

        # NetFlow
        nflowValues = self.prefValues['netflow']
        self.nFrame = LabelFrame(self.rightfieldFrame, text='NetFlow Profile for Open vSwitch', padx=5, pady=5)
        self.nFrame.grid(row=1, column=0, columnspan=2, sticky=EW)

        Label(self.nFrame, text="Target:").grid(row=0, sticky=E)
        self.nflowTarget = Entry(self.nFrame)
        self.nflowTarget.grid(row=0, column=1)
        self.nflowTarget.insert(0, nflowValues['nflowTarget'])

        Label(self.nFrame, text="Active Timeout:").grid(row=1, sticky=E)
        self.nflowTimeout = Entry(self.nFrame)
        self.nflowTimeout.grid(row=1, column=1)
        self.nflowTimeout.insert(0, nflowValues['nflowTimeout'])

        Label(self.nFrame, text="Add ID to Interface:").grid(row=2, sticky=E)
        self.nflowAddId = IntVar()
        self.nflowAddIdButton = Checkbutton(self.nFrame, variable=self.nflowAddId)
        self.nflowAddIdButton.grid(row=2, column=1, sticky=W)
        if nflowValues['nflowAddId'] == '0':
            self.nflowAddIdButton.deselect()
        else:
            self.nflowAddIdButton.select()

        # initial focus
        return self.ipEntry

    def apply(self):
        ipBase = self.ipEntry.get()
        terminalType = self.terminalVar.get()
        startCLI = str(self.cliStart.get())
        enableWmediumd = str(self.enWmediumd.get())
        sw = self.switchType.get()
        ap = self.apType.get()
        wlc = self.wlcType.get()
        dpctl = self.dpctlEntry.get()

        ovsOf10 = str(self.ovsOf10.get())
        ovsOf11 = str(self.ovsOf11.get())
        ovsOf12 = str(self.ovsOf12.get())
        ovsOf13 = str(self.ovsOf13.get())

        sflowValues = {'sflowTarget': self.sflowTarget.get(),
                       'sflowSampling': self.sflowSampling.get(),
                       'sflowHeader': self.sflowHeader.get(),
                       'sflowPolling': self.sflowPolling.get()}
        nflowvalues = {'nflowTarget': self.nflowTarget.get(),
                       'nflowTimeout': self.nflowTimeout.get(),
                       'nflowAddId': str(self.nflowAddId.get())}
        self.result = {'ipBase': ipBase,
                       'terminalType': terminalType,
                       'dpctl': dpctl,
                       'sflow': sflowValues,
                       'netflow': nflowvalues,
                       'enableWmediumd': enableWmediumd,
                       'startCLI': startCLI}
        if sw == 'Userspace':
            self.result['switchType'] = 'user'
        elif sw == 'Userspace inNamespace':
            self.result['switchType'] = 'userns'
        else:
            self.result['switchType'] = 'ovs'

        if ap == 'Userspace':
            self.result['apType'] = 'user'
        elif ap == 'Userspace inNamespace':
            self.result['apType'] = 'userns'
        else:
            self.result['apType'] = 'ovs'

        if wlc == 'Host WLC':
            self.result['wlcType'] = 'hwlc'
        else:
            self.result['wlcType'] = 'ewlc'

        self.ovsOk = True
        if ovsOf11 == "1":
            ovsVer = self.getOvsVersion()
            if StrictVersion(ovsVer) < StrictVersion('2.0'):
                self.ovsOk = False
                messagebox.showerror(title="Error",
                                     message='Open vSwitch version 2.0+ required. You have ' + ovsVer + '.')
        if ovsOf12 == "1" or ovsOf13 == "1":
            ovsVer = self.getOvsVersion()
            if StrictVersion(ovsVer) < StrictVersion('1.10'):
                self.ovsOk = False
                messagebox.showerror(title="Error",
                                     message='Open vSwitch version 1.10+ required. You have ' + ovsVer + '.')

        if self.ovsOk:
            self.result['openFlowVersions'] = {'ovsOf10': ovsOf10,
                                               'ovsOf11': ovsOf11,
                                               'ovsOf12': ovsOf12,
                                               'ovsOf13': ovsOf13}
        else:
            self.result = None

    @staticmethod
    def getOvsVersion():
        """Return OVS version"""
        outp = quietRun("ovs-vsctl --version")
        r = r'ovs-vsctl \(Open vSwitch\) (.*)'
        m = re.search(r, outp)
        if m is None:
            warn('Version check failed')
            return None

        info('Open vSwitch version is ' + m.group(1), '\n')
        return m.group(1)


class CustomDialog(object):

    # TODO: Fix button placement and Title and window focus lock
    def __init__(self, master, _title):
        self.top = Toplevel(master)

        self.bodyFrame = Frame(self.top)
        self.bodyFrame.grid(row=0, column=0, sticky='nswe')
        self.body(self.bodyFrame)

        # return self.b # initial focus
        buttonFrame = Frame(self.top, relief='ridge', bd=3, bg='lightgrey')
        buttonFrame.grid(row=1, column=0, sticky='nswe')

        okButton = Button(buttonFrame, width=8, text='OK', relief='groove',
                          bd=4, command=self.okAction)
        okButton.grid(row=0, column=0, sticky=E)

        canlceButton = Button(buttonFrame, width=8, text='Cancel', relief='groove',
                              bd=4, command=self.cancelAction)
        canlceButton.grid(row=0, column=1, sticky=W)

    def body(self, master):
        self.rootFrame = master

    def apply(self):
        self.top.destroy()

    def cancelAction(self):
        self.top.destroy()

    def okAction(self):
        self.apply()
        self.top.destroy()


class HostDialog(CustomDialog):

    def __init__(self, master, title, prefDefaults):

        self.prefValues = prefDefaults
        self.result = None

        CustomDialog.__init__(self, master, title)

    def body(self, master):
        self.rootFrame = master
        n = ttk.Notebook(self.rootFrame)
        self.propFrame = Frame(n)
        self.vlanFrame = Frame(n)
        self.interfaceFrame = Frame(n)
        self.mountFrame = Frame(n)
        n.add(self.propFrame, text='Properties')
        n.add(self.vlanFrame, text='VLAN Interfaces')
        n.add(self.interfaceFrame, text='External Interfaces')
        n.add(self.mountFrame, text='Private Directories')
        n.pack()

        ### TAB 1
        # Field for Hostname
        Label(self.propFrame, text="Hostname:").grid(row=0, sticky=E)
        self.hostnameEntry = Entry(self.propFrame)
        self.hostnameEntry.grid(row=0, column=1)
        if 'hostname' in self.prefValues:
            self.hostnameEntry.insert(0, self.prefValues['hostname'])

        # Field for Switch IP
        Label(self.propFrame, text="IP Address:").grid(row=1, sticky=E)
        self.ipEntry = Entry(self.propFrame)
        self.ipEntry.grid(row=1, column=1)
        if 'ip' in self.prefValues:
            self.ipEntry.insert(0, self.prefValues['ip'])

        # Field for default route
        Label(self.propFrame, text="Default Route:").grid(row=2, sticky=E)
        self.routeEntry = Entry(self.propFrame)
        self.routeEntry.grid(row=2, column=1)
        if 'defaultRoute' in self.prefValues:
            self.routeEntry.insert(0, self.prefValues['defaultRoute'])

        # Field for CPU
        Label(self.propFrame, text="Amount CPU:").grid(row=3, sticky=E)
        self.cpuEntry = Entry(self.propFrame)
        self.cpuEntry.grid(row=3, column=1)
        if 'cpu' in self.prefValues:
            self.cpuEntry.insert(0, str(self.prefValues['cpu']))
        # Selection of Scheduler
        if 'sched' in self.prefValues:
            sched = self.prefValues['sched']
        else:
            sched = 'host'
        self.schedVar = StringVar(self.propFrame)
        self.schedOption = OptionMenu(self.propFrame, self.schedVar, "host", "cfs", "rt")
        self.schedOption.grid(row=3, column=2, sticky=W)
        self.schedVar.set(sched)

        # Selection of Cores
        Label(self.propFrame, text="Cores:").grid(row=4, sticky=E)
        self.coreEntry = Entry(self.propFrame)
        self.coreEntry.grid(row=4, column=1)
        if 'cores' in self.prefValues:
            self.coreEntry.insert(1, self.prefValues['cores'])

        # Start command
        Label(self.propFrame, text="Start Command:").grid(row=5, sticky=E)
        self.startEntry = Entry(self.propFrame)
        self.startEntry.grid(row=5, column=1, sticky='nswe', columnspan=3)
        if 'startCommand' in self.prefValues:
            self.startEntry.insert(0, str(self.prefValues['startCommand']))
        # Stop command
        Label(self.propFrame, text="Stop Command:").grid(row=6, sticky=E)
        self.stopEntry = Entry(self.propFrame)
        self.stopEntry.grid(row=6, column=1, sticky='nswe', columnspan=3)
        if 'stopCommand' in self.prefValues:
            self.stopEntry.insert(0, str(self.prefValues['stopCommand']))

        ### TAB 2
        # External Interfaces
        self.externalInterfaces = 0
        Label(self.interfaceFrame, text="External Interface:").grid(row=0, column=0, sticky=E)
        self.b = Button(self.interfaceFrame, text='Add', command=self.addInterface)
        self.b.grid(row=0, column=1)

        self.interfaceFrame = VerticalScrolledTable(self.interfaceFrame, rows=0, columns=1, title='External Interfaces')
        self.interfaceFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.tableFrame = self.interfaceFrame.interior
        self.tableFrame.addRow(value=['Interface Name'], readonly=True)

        # Add defined interfaces
        externalInterfaces = []
        if 'externalInterfaces' in self.prefValues:
            externalInterfaces = self.prefValues['externalInterfaces']

        for externalInterface in externalInterfaces:
            self.tableFrame.addRow(value=[externalInterface])

        ### TAB 3
        # VLAN Interfaces
        self.vlanInterfaces = 0
        Label(self.vlanFrame, text="VLAN Interface:").grid(row=0, column=0, sticky=E)
        self.vlanButton = Button(self.vlanFrame, text='Add', command=self.addVlanInterface)
        self.vlanButton.grid(row=0, column=1)

        self.vlanFrame = VerticalScrolledTable(self.vlanFrame, rows=0, columns=2, title='VLAN Interfaces')
        self.vlanFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.vlanTableFrame = self.vlanFrame.interior
        self.vlanTableFrame.addRow(value=['IP Address', 'VLAN ID'], readonly=True)

        vlanInterfaces = []
        if 'vlanInterfaces' in self.prefValues:
            vlanInterfaces = self.prefValues['vlanInterfaces']
        for vlanInterface in vlanInterfaces:
            self.vlanTableFrame.addRow(value=vlanInterface)

        ### TAB 4
        # Private Directories
        self.privateDirectories = 0
        Label(self.mountFrame, text="Private Directory:").grid(row=0, column=0, sticky=E)
        self.mountButton = Button(self.mountFrame, text='Add', command=self.addDirectory)
        self.mountButton.grid(row=0, column=1)

        self.mountFrame = VerticalScrolledTable(self.mountFrame, rows=0, columns=2, title='Directories')
        self.mountFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.mountTableFrame = self.mountFrame.interior
        self.mountTableFrame.addRow(value=['Mount', 'Persistent Directory'], readonly=True)

        directoryList = []
        if 'privateDirectory' in self.prefValues:
            directoryList = self.prefValues['privateDirectory']
        for privateDir in directoryList:
            if isinstance(privateDir, tuple):
                self.mountTableFrame.addRow(value=privateDir)
            else:
                self.mountTableFrame.addRow(value=[privateDir, ''])

    def addDirectory(self):
        self.mountTableFrame.addRow()

    def addVlanInterface(self):
        self.vlanTableFrame.addRow()

    def addInterface(self):
        self.tableFrame.addRow()

    def apply(self):
        externalInterfaces = []
        for row in range(self.tableFrame.rows):
            if (len(self.tableFrame.get(row, 0)) > 0 and row > 0):
                externalInterfaces.append(self.tableFrame.get(row, 0))
        vlanInterfaces = []
        for row in range(self.vlanTableFrame.rows):
            if (len(self.vlanTableFrame.get(row, 0)) > 0
                    and len(self.vlanTableFrame.get(row, 1)) > 0 and row > 0):
                vlanInterfaces.append([self.vlanTableFrame.get(row, 0), self.vlanTableFrame.get(row, 1)])
        privateDirectories = []
        for row in range(self.mountTableFrame.rows):
            if len(self.mountTableFrame.get(row, 0)) > 0 and row > 0:
                if len(self.mountTableFrame.get(row, 1)) > 0:
                    privateDirectories.append((self.mountTableFrame.get(row, 0), self.mountTableFrame.get(row, 1)))
                else:
                    privateDirectories.append(self.mountTableFrame.get(row, 0))

        results = {'cpu': self.cpuEntry.get(),
                   'cores': self.coreEntry.get(),
                   'sched': self.schedVar.get(),
                   'hostname': self.hostnameEntry.get(),
                   'ip': self.ipEntry.get(),
                   'defaultRoute': self.routeEntry.get(),
                   'startCommand': self.startEntry.get(),
                   'stopCommand': self.stopEntry.get(),
                   'privateDirectory': privateDirectories,
                   'externalInterfaces': externalInterfaces,
                   'vlanInterfaces': vlanInterfaces}
        self.result = results


class StationDialog(CustomDialog):

    def __init__(self, master, title, prefDefaults):

        self.prefValues = prefDefaults
        self.result = None

        CustomDialog.__init__(self, master, title)

    def body(self, master):
        self.rootFrame = master
        n = ttk.Notebook(self.rootFrame)
        self.propFrame = Frame(n)
        self.authFrame = Frame(n)
        self.vlanFrame = Frame(n)
        self.interfaceFrame = Frame(n)
        self.mountFrame = Frame(n)
        n.add(self.propFrame, text='Properties')
        n.add(self.authFrame, text='Authentication')
        n.add(self.vlanFrame, text='VLAN Interfaces')
        n.add(self.interfaceFrame, text='External Interfaces')
        n.add(self.mountFrame, text='Private Directories')
        n.pack()

        ### TAB 1
        # Field for Hostname
        rowCount = 0
        Label(self.propFrame, text="Name:").grid(row=rowCount, sticky=E)
        self.hostnameEntry = Entry(self.propFrame)
        self.hostnameEntry.grid(row=rowCount, column=1)
        if 'hostname' in self.prefValues:
            self.hostnameEntry.insert(0, self.prefValues['hostname'])

        # Field for SSID
        # rowCount += 1
        # Label(self.propFrame, text="SSID:").grid(row=rowCount, sticky=E)
        # self.ssidEntry = Entry(self.propFrame)
        # self.ssidEntry.grid(row=rowCount, column=1)
        # self.ssidEntry.insert(0, self.prefValues['ssid'])

        # Field for channel
        # rowCount += 1
        # Label(self.propFrame, text="Channel:").grid(row=rowCount, sticky=E)
        # self.channelEntry = Entry(self.propFrame)
        # self.channelEntry.grid(row=rowCount, column=1)
        # self.channelEntry.insert(0, self.prefValues['channel'])

        # Selection of mode
        # rowCount += 1
        # Label(self.propFrame, text="Mode:").grid(row=rowCount, sticky=E)
        # self.mode = StringVar(self.propFrame)
        # self.modeMenu = OptionMenu(self.propFrame, self.mode, "g", "a",
        #                           "b", "n")
        # self.modeMenu.grid(row=rowCount, column=1, sticky=W)
        # if 'mode' in self.prefValues:
        #    authPref = self.prefValues['mode']
        #    if authPref == 'g':
        #        self.mode.set("g")
        #    elif authPref == 'a':
        #        self.mode.set("a")
        #    elif authPref == 'b':
        #        self.mode.set("b")
        #    elif authPref == 'n':
        #        self.mode.set("n")
        #    else:
        #        self.mode.set("g")
        # else:
        #    self.mode.set("g")
        self.mode = 'g'

        # Field for Wlans
        rowCount += 1
        Label(self.propFrame, text="Wlans:").grid(row=rowCount, sticky=E)
        self.wlansEntry = Entry(self.propFrame)
        self.wlansEntry.grid(row=rowCount, column=1)
        self.wlansEntry.insert(0, self.prefValues['wlans'])

        # Field for Wpans
        rowCount += 1
        Label(self.propFrame, text="Wpans:").grid(row=rowCount, sticky=E)
        self.wpansEntry = Entry(self.propFrame)
        self.wpansEntry.grid(row=rowCount, column=1)
        self.wpansEntry.insert(0, self.prefValues['wpans'])

        # Field for signal range
        rowCount += 1
        Label(self.propFrame, text="Signal Range:").grid(row=rowCount, sticky=E)
        self.rangeEntry = Entry(self.propFrame)
        self.rangeEntry.grid(row=rowCount, column=1)
        self.rangeEntry.insert(0, self.prefValues['range'])

        # Field for Station IP
        rowCount += 1
        Label(self.propFrame, text="IP Address:").grid(row=rowCount, sticky=E)
        self.ipEntry = Entry(self.propFrame)
        self.ipEntry.grid(row=rowCount, column=1)
        if 'ip' in self.prefValues:
            self.ipEntry.insert(0, self.prefValues['ip'])

        # Field for default route
        rowCount += 1
        Label(self.propFrame, text="Default Route:").grid(row=rowCount, sticky=E)
        self.routeEntry = Entry(self.propFrame)
        self.routeEntry.grid(row=rowCount, column=1)
        if 'defaultRoute' in self.prefValues:
            self.routeEntry.insert(0, self.prefValues['defaultRoute'])

        # Field for CPU
        rowCount += 1
        Label(self.propFrame, text="Amount CPU:").grid(row=rowCount, sticky=E)
        self.cpuEntry = Entry(self.propFrame)
        self.cpuEntry.grid(row=rowCount, column=1)
        if 'cpu' in self.prefValues:
            self.cpuEntry.insert(0, str(self.prefValues['cpu']))
        # Selection of Scheduler
        if 'sched' in self.prefValues:
            sched = self.prefValues['sched']
        else:
            sched = 'station'
        self.schedVar = StringVar(self.propFrame)
        self.schedOption = OptionMenu(self.propFrame, self.schedVar, "station", "cfs", "rt")
        self.schedOption.grid(row=rowCount, column=2, sticky=W)
        self.schedVar.set(sched)

        # Selection of Cores
        rowCount += 1
        Label(self.propFrame, text="Cores:").grid(row=rowCount, sticky=E)
        self.coreEntry = Entry(self.propFrame)
        self.coreEntry.grid(row=rowCount, column=1)
        if 'cores' in self.prefValues:
            self.coreEntry.insert(1, self.prefValues['cores'])

        # Start command
        rowCount += 1
        Label(self.propFrame, text="Start Command:").grid(row=rowCount, sticky=E)
        self.startEntry = Entry(self.propFrame)
        self.startEntry.grid(row=rowCount, column=1, sticky='nswe', columnspan=3)
        if 'startCommand' in self.prefValues:
            self.startEntry.insert(0, str(self.prefValues['startCommand']))
        # Stop command
        rowCount += 1
        Label(self.propFrame, text="Stop Command:").grid(row=rowCount, sticky=E)
        self.stopEntry = Entry(self.propFrame)
        self.stopEntry.grid(row=rowCount, column=1, sticky='nswe', columnspan=3)
        if 'stopCommand' in self.prefValues:
            self.stopEntry.insert(0, str(self.prefValues['stopCommand']))

        ### TAB Auth
        rowCount = 0
        # Selection of authentication
        Label(self.authFrame, text="Authentication:").grid(row=rowCount, sticky=E)
        self.authentication = StringVar(self.authFrame)
        self.authenticationMenu = OptionMenu(self.authFrame,
                                             self.authentication, "none", "WEP",
                                             "WPA", "WPA2", "8021x")
        self.authenticationMenu.grid(row=rowCount, column=1, sticky=W)
        if 'authentication' in self.prefValues:
            authPref = self.prefValues['authentication']
            if authPref == 'WEP':
                self.authentication.set("WEP")
            elif authPref == 'WPA':
                self.authentication.set("WPA")
            elif authPref == 'WPA2':
                self.authentication.set("WPA2")
            elif authPref == '8021x':
                self.authentication.set("8021x")
            else:
                self.authentication.set("none")
        else:
            self.authentication.set("none")
        rowCount += 1

        # Field for username
        Label(self.authFrame, text="Username:").grid(row=rowCount, sticky=E)
        self.userEntry = Entry(self.authFrame)
        self.userEntry.grid(row=rowCount, column=1)
        if 'user' in self.prefValues:
            self.userEntry.insert(0, self.prefValues['user'])

        # Field for passwd
        rowCount += 1
        Label(self.authFrame, text="Password:").grid(row=rowCount, sticky=E)
        self.passwdEntry = Entry(self.authFrame)
        self.passwdEntry.grid(row=rowCount, column=1)
        if 'passwd' in self.prefValues:
            self.passwdEntry.insert(0, self.prefValues['passwd'])

        ### TAB 2
        # External Interfaces
        self.externalInterfaces = 0
        Label(self.interfaceFrame, text="External Interface:").grid(row=0, column=0, sticky=E)
        self.b = Button(self.interfaceFrame, text='Add', command=self.addInterface)
        self.b.grid(row=0, column=1)

        self.interfaceFrame = VerticalScrolledTable(self.interfaceFrame, rows=0, columns=1, title='External Interfaces')
        self.interfaceFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.tableFrame = self.interfaceFrame.interior
        self.tableFrame.addRow(value=['Interface Name'], readonly=True)

        # Add defined interfaces
        externalInterfaces = []
        if 'externalInterfaces' in self.prefValues:
            externalInterfaces = self.prefValues['externalInterfaces']

        for externalInterface in externalInterfaces:
            self.tableFrame.addRow(value=[externalInterface])

        ### TAB 3
        # VLAN Interfaces
        self.vlanInterfaces = 0
        Label(self.vlanFrame, text="VLAN Interface:").grid(row=0, column=0, sticky=E)
        self.vlanButton = Button(self.vlanFrame, text='Add', command=self.addVlanInterface)
        self.vlanButton.grid(row=0, column=1)

        self.vlanFrame = VerticalScrolledTable(self.vlanFrame, rows=0, columns=2, title='VLAN Interfaces')
        self.vlanFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.vlanTableFrame = self.vlanFrame.interior
        self.vlanTableFrame.addRow(value=['IP Address', 'VLAN ID'], readonly=True)

        vlanInterfaces = []
        if 'vlanInterfaces' in self.prefValues:
            vlanInterfaces = self.prefValues['vlanInterfaces']
        for vlanInterface in vlanInterfaces:
            self.vlanTableFrame.addRow(value=vlanInterface)

        ### TAB 4
        # Private Directories
        self.privateDirectories = 0
        Label(self.mountFrame, text="Private Directory:").grid(row=0, column=0, sticky=E)
        self.mountButton = Button(self.mountFrame, text='Add', command=self.addDirectory)
        self.mountButton.grid(row=0, column=1)

        self.mountFrame = VerticalScrolledTable(self.mountFrame, rows=0, columns=2, title='Directories')
        self.mountFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.mountTableFrame = self.mountFrame.interior
        self.mountTableFrame.addRow(value=['Mount', 'Persistent Directory'], readonly=True)

        directoryList = []
        if 'privateDirectory' in self.prefValues:
            directoryList = self.prefValues['privateDirectory']
        for privateDir in directoryList:
            if isinstance(privateDir, tuple):
                self.mountTableFrame.addRow(value=privateDir)
            else:
                self.mountTableFrame.addRow(value=[privateDir, ''])

    def addDirectory(self):
        self.mountTableFrame.addRow()

    def addVlanInterface(self):
        self.vlanTableFrame.addRow()

    def addInterface(self):
        self.tableFrame.addRow()

    def apply(self):
        externalInterfaces = []
        for row in range(self.tableFrame.rows):
            if (len(self.tableFrame.get(row, 0)) > 0 and row > 0):
                externalInterfaces.append(self.tableFrame.get(row, 0))
        vlanInterfaces = []
        for row in range(self.vlanTableFrame.rows):
            if (len(self.vlanTableFrame.get(row, 0)) > 0 and
                    len(self.vlanTableFrame.get(row, 1)) > 0 and row > 0):
                vlanInterfaces.append([self.vlanTableFrame.get(row, 0), self.vlanTableFrame.get(row, 1)])
        privateDirectories = []
        for row in range(self.mountTableFrame.rows):
            if len(self.mountTableFrame.get(row, 0)) > 0 and row > 0:
                if len(self.mountTableFrame.get(row, 1)) > 0:
                    privateDirectories.append((self.mountTableFrame.get(row, 0), self.mountTableFrame.get(row, 1)))
                else:
                    privateDirectories.append(self.mountTableFrame.get(row, 0))

        results = {'cpu': self.cpuEntry.get(),
                   'cores': self.coreEntry.get(),
                   'sched': self.schedVar.get(),
                   'hostname': self.hostnameEntry.get(),
                   'ip': self.ipEntry.get(),
                   'defaultRoute': self.routeEntry.get(),
                   'startCommand': self.startEntry.get(),
                   'stopCommand': self.stopEntry.get(),
                   'privateDirectory': privateDirectories,
                   'externalInterfaces': externalInterfaces,
                   'vlanInterfaces': vlanInterfaces}
        # results['ssid'] = str(self.ssidEntry.get())
        results['passwd'] = str(self.passwdEntry.get())
        results['user'] = str(self.userEntry.get())
        results['wlans'] = self.wlansEntry.get()
        results['mode'] = 'g'
        results['wpans'] = self.wpansEntry.get()
        results['range'] = str(self.rangeEntry.get())
        self.result = results


class SwitchDialog(CustomDialog):

    def __init__(self, master, title, prefDefaults):

        self.prefValues = prefDefaults
        self.result = None
        CustomDialog.__init__(self, master, title)

    def body(self, master):
        self.rootFrame = master
        self.leftfieldFrame = Frame(self.rootFrame)
        self.rightfieldFrame = Frame(self.rootFrame)
        self.leftfieldFrame.grid(row=0, column=0, sticky='nswe')
        self.rightfieldFrame.grid(row=0, column=1, sticky='nswe')

        rowCount = 0
        externalInterfaces = []
        if 'externalInterfaces' in self.prefValues:
            externalInterfaces = self.prefValues['externalInterfaces']

        # Field for Hostname
        Label(self.leftfieldFrame, text="Hostname:").grid(row=rowCount, sticky=E)
        self.hostnameEntry = Entry(self.leftfieldFrame)
        self.hostnameEntry.grid(row=rowCount, column=1)
        self.hostnameEntry.insert(0, self.prefValues['hostname'])
        rowCount += 1

        # Field for DPID
        Label(self.leftfieldFrame, text="DPID:").grid(row=rowCount, sticky=E)
        self.dpidEntry = Entry(self.leftfieldFrame)
        self.dpidEntry.grid(row=rowCount, column=1)
        if 'dpid' in self.prefValues:
            self.dpidEntry.insert(0, self.prefValues['dpid'])
        rowCount += 1

        # Field for Netflow
        Label(self.leftfieldFrame, text="Enable NetFlow:").grid(row=rowCount, sticky=E)
        self.nflow = IntVar()
        self.nflowButton = Checkbutton(self.leftfieldFrame, variable=self.nflow)
        self.nflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'netflow' in self.prefValues:
            if self.prefValues['netflow'] == '0':
                self.nflowButton.deselect()
            else:
                self.nflowButton.select()
        else:
            self.nflowButton.deselect()
        rowCount += 1

        # Field for sflow
        Label(self.leftfieldFrame, text="Enable sFlow:").grid(row=rowCount, sticky=E)
        self.sflow = IntVar()
        self.sflowButton = Checkbutton(self.leftfieldFrame, variable=self.sflow)
        self.sflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'sflow' in self.prefValues:
            if self.prefValues['sflow'] == '0':
                self.sflowButton.deselect()
            else:
                self.sflowButton.select()
        else:
            self.sflowButton.deselect()
        rowCount += 1

        # Selection of switch type
        Label(self.leftfieldFrame, text="Switch Type:").grid(row=rowCount, sticky=E)
        self.switchType = StringVar(self.leftfieldFrame)
        self.switchTypeMenu = OptionMenu(self.leftfieldFrame, self.switchType, "Default",
                                         "Open vSwitch Kernel Mode", "Userspace", "Userspace inNamespace")
        self.switchTypeMenu.grid(row=rowCount, column=1, sticky=W)
        if 'switchType' in self.prefValues:
            switchTypePref = self.prefValues['switchType']
            if switchTypePref == 'userns':
                self.switchType.set("Userspace inNamespace")
            elif switchTypePref == 'user':
                self.switchType.set("Userspace")
            elif switchTypePref == 'ovs':
                self.switchType.set("Open vSwitch Kernel Mode")
            else:
                self.switchType.set("Default")
        else:
            self.switchType.set("Default")
        rowCount += 1

        # Field for Switch IP
        Label(self.leftfieldFrame, text="IP Address:").grid(row=rowCount, sticky=E)
        self.ipEntry = Entry(self.leftfieldFrame)
        self.ipEntry.grid(row=rowCount, column=1)
        if 'switchIP' in self.prefValues:
            self.ipEntry.insert(0, self.prefValues['switchIP'])
        rowCount += 1

        # Field for DPCTL port
        Label(self.leftfieldFrame, text="DPCTL port:").grid(row=rowCount, sticky=E)
        self.dpctlEntry = Entry(self.leftfieldFrame)
        self.dpctlEntry.grid(row=rowCount, column=1)
        if 'dpctl' in self.prefValues:
            self.dpctlEntry.insert(0, self.prefValues['dpctl'])
        rowCount += 1

        # External Interfaces
        Label(self.rightfieldFrame, text="External Interface:").grid(row=0, sticky=E)
        self.b = Button(self.rightfieldFrame, text='Add', command=self.addInterface)
        self.b.grid(row=0, column=1)

        self.interfaceFrame = VerticalScrolledTable(self.rightfieldFrame, rows=0, columns=1,
                                                    title='External Interfaces')
        self.interfaceFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.tableFrame = self.interfaceFrame.interior

        # Add defined interfaces
        for externalInterface in externalInterfaces:
            self.tableFrame.addRow(value=[externalInterface])

        self.commandFrame = Frame(self.rootFrame)
        self.commandFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.commandFrame.columnconfigure(1, weight=1)
        # Start command
        Label(self.commandFrame, text="Start Command:").grid(row=0, column=0, sticky=W)
        self.startEntry = Entry(self.commandFrame)
        self.startEntry.grid(row=0, column=1, sticky='nsew')
        if 'startCommand' in self.prefValues:
            self.startEntry.insert(0, str(self.prefValues['startCommand']))
        # Stop command
        Label(self.commandFrame, text="Stop Command:").grid(row=1, column=0, sticky=W)
        self.stopEntry = Entry(self.commandFrame)
        self.stopEntry.grid(row=1, column=1, sticky='nsew')
        if 'stopCommand' in self.prefValues:
            self.stopEntry.insert(0, str(self.prefValues['stopCommand']))

    def addInterface(self):
        self.tableFrame.addRow()

    def defaultDpid(self, name):
        """Derive dpid from switch name, s1 -> 1"""
        assert self  # satisfy pylint and allow contextual override
        try:
            dpid = int(re.findall(r'\d+', name)[0])
            dpid = hex(dpid)[2:]
            return dpid
        except IndexError:
            return None
            # raise Exception( 'Unable to derive default datapath ID - '
            #                 'please either specify a dpid or use a '
            #                 'canonical switch name such as s23.' )

    def apply(self):
        externalInterfaces = []
        for row in range(self.tableFrame.rows):
            # debug( 'Interface is ' + self.tableFrame.get(row, 0), '\n' )
            if len(self.tableFrame.get(row, 0)) > 0:
                externalInterfaces.append(self.tableFrame.get(row, 0))

        dpid = self.dpidEntry.get()
        if (self.defaultDpid(self.hostnameEntry.get()) is None
                and len(dpid) == 0):
            messagebox.showerror(title="Error",
                                 message='Unable to derive default datapath ID - '
                                         'please either specify a DPID or use a '
                                         'canonical switch name such as s23.')

        results = {'externalInterfaces': externalInterfaces,
                   'hostname': self.hostnameEntry.get(),
                   'dpid': dpid,
                   'startCommand': self.startEntry.get(),
                   'stopCommand': self.stopEntry.get(),
                   'sflow': str(self.sflow.get()),
                   'netflow': str(self.nflow.get()),
                   'dpctl': self.dpctlEntry.get(),
                   'switchIP': self.ipEntry.get()}
        sw = self.switchType.get()
        if sw == 'Userspace inNamespace':
            results['switchType'] = 'userns'
        elif sw == 'Userspace':
            results['switchType'] = 'user'
        elif sw == 'Open vSwitch Kernel Mode':
            results['switchType'] = 'ovs'
        else:
            results['switchType'] = 'default'
        self.result = results


class WLCDialog(CustomDialog):

    def __init__(self, master, title, prefDefaults):

        self.prefValues = prefDefaults
        self.result = None
        CustomDialog.__init__(self, master, title)

    def body(self, master):
        self.rootFrame = master
        self.leftfieldFrame = Frame(self.rootFrame)
        self.rightfieldFrame = Frame(self.rootFrame)
        self.leftfieldFrame.grid(row=0, column=0, sticky='nswe')
        self.rightfieldFrame.grid(row=0, column=1, sticky='nswe')

        rowCount = 0
        externalInterfaces = []
        if 'externalInterfaces' in self.prefValues:
            externalInterfaces = self.prefValues['externalInterfaces']

        # Field for Hostname
        Label(self.leftfieldFrame, text="Hostname:").grid(row=rowCount, sticky=E)
        self.hostnameEntry = Entry(self.leftfieldFrame)
        self.hostnameEntry.grid(row=rowCount, column=1)
        self.hostnameEntry.insert(0, self.prefValues['hostname'])
        rowCount += 1

        # Field for DPID
        Label(self.leftfieldFrame, text="DPID:").grid(row=rowCount, sticky=E)
        self.dpidEntry = Entry(self.leftfieldFrame)
        self.dpidEntry.grid(row=rowCount, column=1)
        if 'dpid' in self.prefValues:
            self.dpidEntry.insert(0, self.prefValues['dpid'])
        rowCount += 1

        # Field for Netflow
        Label(self.leftfieldFrame, text="Enable NetFlow:").grid(row=rowCount, sticky=E)
        self.nflow = IntVar()
        self.nflowButton = Checkbutton(self.leftfieldFrame, variable=self.nflow)
        self.nflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'netflow' in self.prefValues:
            if self.prefValues['netflow'] == '0':
                self.nflowButton.deselect()
            else:
                self.nflowButton.select()
        else:
            self.nflowButton.deselect()
        rowCount += 1

        # Field for sflow
        Label(self.leftfieldFrame, text="Enable sFlow:").grid(row=rowCount, sticky=E)
        self.sflow = IntVar()
        self.sflowButton = Checkbutton(self.leftfieldFrame, variable=self.sflow)
        self.sflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'sflow' in self.prefValues:
            if self.prefValues['sflow'] == '0':
                self.sflowButton.deselect()
            else:
                self.sflowButton.select()
        else:
            self.sflowButton.deselect()
        rowCount += 1

        # Selection of wlc type
        Label(self.leftfieldFrame, text="WLC Type:").grid(row=rowCount, sticky=E)
        self.wlcType = StringVar(self.leftfieldFrame)
        self.wlcTypeMenu = OptionMenu(self.leftfieldFrame, self.wlcType, "Host WLC",
                                      "External WLC")
        self.wlcTypeMenu.grid(row=rowCount, column=1, sticky=W)
        if 'wlcType' in self.prefValues:
            wlcTypePref = self.prefValues['wlcType']
            if wlcTypePref == 'hwlc':
                self.wlcType.set("Host WLC")
            else:
                self.wlcType.set("External WLC")
        else:
            self.wlcType.set("Host WLC")
        rowCount += 1

        # Field for Switch IP
        Label(self.leftfieldFrame, text="IP Address:").grid(row=rowCount, sticky=E)
        self.ipEntry = Entry(self.leftfieldFrame)
        self.ipEntry.grid(row=rowCount, column=1)
        if 'wlcIP' in self.prefValues:
            self.ipEntry.insert(0, self.prefValues['wlcIP'])
        rowCount += 1

        # Field for DPCTL port
        Label(self.leftfieldFrame, text="DPCTL port:").grid(row=rowCount, sticky=E)
        self.dpctlEntry = Entry(self.leftfieldFrame)
        self.dpctlEntry.grid(row=rowCount, column=1)
        if 'dpctl' in self.prefValues:
            self.dpctlEntry.insert(0, self.prefValues['dpctl'])
        rowCount += 1

        # External Interfaces
        Label(self.rightfieldFrame, text="External Interface:").grid(row=0, sticky=E)
        self.b = Button(self.rightfieldFrame, text='Add', command=self.addInterface)
        self.b.grid(row=0, column=1)

        self.interfaceFrame = VerticalScrolledTable(self.rightfieldFrame, rows=0, columns=1,
                                                    title='External Interfaces')
        self.interfaceFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.tableFrame = self.interfaceFrame.interior

        # Add defined interfaces
        for externalInterface in externalInterfaces:
            self.tableFrame.addRow(value=[externalInterface])

        self.commandFrame = Frame(self.rootFrame)
        self.commandFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.commandFrame.columnconfigure(1, weight=1)
        # Start command
        Label(self.commandFrame, text="Start Command:").grid(row=0, column=0, sticky=W)
        self.startEntry = Entry(self.commandFrame)
        self.startEntry.grid(row=0, column=1, sticky='nsew')
        if 'startCommand' in self.prefValues:
            self.startEntry.insert(0, str(self.prefValues['startCommand']))
        # Stop command
        Label(self.commandFrame, text="Stop Command:").grid(row=1, column=0, sticky=W)
        self.stopEntry = Entry(self.commandFrame)
        self.stopEntry.grid(row=1, column=1, sticky='nsew')
        if 'stopCommand' in self.prefValues:
            self.stopEntry.insert(0, str(self.prefValues['stopCommand']))

    def addInterface(self):
        self.tableFrame.addRow()

    def defaultDpid(self, name):
        """Derive dpid from switch name, s1 -> 1"""
        assert self  # satisfy pylint and allow contextual override
        try:
            dpid = int(re.findall(r'\d+', name)[0])
            dpid = hex(dpid)[2:]
            return dpid
        except IndexError:
            return None
            # raise Exception( 'Unable to derive default datapath ID - '
            #                 'please either specify a dpid or use a '
            #                 'canonical switch name such as s23.' )

    def apply(self):
        externalInterfaces = []
        for row in range(self.tableFrame.rows):
            # debug( 'Interface is ' + self.tableFrame.get(row, 0), '\n' )
            if len(self.tableFrame.get(row, 0)) > 0:
                externalInterfaces.append(self.tableFrame.get(row, 0))

        dpid = self.dpidEntry.get()
        if (self.defaultDpid(self.hostnameEntry.get()) is None
                and len(dpid) == 0):
            messagebox.showerror(title="Error",
                                 message='Unable to derive default datapath ID - '
                                         'please either specify a DPID or use a '
                                         'canonical wlc name such as wlc23.')

        results = {'externalInterfaces': externalInterfaces,
                   'hostname': self.hostnameEntry.get(),
                   'dpid': dpid,
                   'startCommand': self.startEntry.get(),
                   'stopCommand': self.stopEntry.get(),
                   'sflow': str(self.sflow.get()),
                   'netflow': str(self.nflow.get()),
                   'dpctl': self.dpctlEntry.get(),
                   'switchIP': self.ipEntry.get()}
        sw = self.wlcType.get()
        if sw == 'Host WLC':
            results['wlcType'] = 'hwlc'
        else:
            results['wlcType'] = 'ewlc'
        self.result = results


class APDialog(CustomDialog):

    def __init__(self, master, title, prefDefaults):

        self.prefValues = prefDefaults
        self.result = None
        CustomDialog.__init__(self, master, title)

    def body(self, master):
        self.rootFrame = master
        n = ttk.Notebook(self.rootFrame)
        self.propFrame = Frame(n)
        self.authFrame = Frame(n)
        n.add(self.propFrame, text='Properties')
        n.add(self.authFrame, text='Authentication')
        n.pack()

        self.leftfieldFrame = Frame(self.propFrame)
        self.rightfieldFrame = Frame(self.propFrame)
        self.leftfieldFrame.grid(row=0, column=0, sticky='nswe')
        self.rightfieldFrame.grid(row=0, column=1, sticky='nswe')

        rowCount = 0
        externalInterfaces = []
        if 'externalInterfaces' in self.prefValues:
            externalInterfaces = self.prefValues['externalInterfaces']

        # Field for Hostname
        Label(self.leftfieldFrame, text="Hostname:").grid(row=rowCount, sticky=E)
        self.hostnameEntry = Entry(self.leftfieldFrame)
        self.hostnameEntry.grid(row=rowCount, column=1)
        self.hostnameEntry.insert(0, self.prefValues['hostname'])
        rowCount += 1

        # Field for wlans
        Label(self.leftfieldFrame, text="Wlans:").grid(row=rowCount, sticky=E)
        self.wlansEntry = Entry(self.leftfieldFrame)
        self.wlansEntry.grid(row=rowCount, column=1)
        self.wlansEntry.insert(0, self.prefValues['wlans'])
        rowCount += 1

        # Field for SSID
        Label(self.leftfieldFrame, text="SSID:").grid(row=rowCount, sticky=E)
        self.ssidEntry = Entry(self.leftfieldFrame)
        self.ssidEntry.grid(row=rowCount, column=1)
        self.ssidEntry.insert(0, self.prefValues['ssid'])
        rowCount += 1

        # Field for channel
        Label(self.leftfieldFrame, text="Channel:").grid(row=rowCount, sticky=E)
        self.channelEntry = Entry(self.leftfieldFrame)
        self.channelEntry.grid(row=rowCount, column=1)
        self.channelEntry.insert(0, self.prefValues['channel'])
        rowCount += 1

        # Selection of mode
        Label(self.leftfieldFrame, text="Mode:").grid(row=rowCount, sticky=E)
        self.mode = StringVar(self.leftfieldFrame)
        self.modeMenu = OptionMenu(self.leftfieldFrame, self.mode, "g", "a", "b", "n", "ac", "ax", "be")
        self.modeMenu.grid(row=rowCount, column=1, sticky=W)
        if 'mode' in self.prefValues:
            modePref = self.prefValues['mode']
            if modePref == 'g':
                self.mode.set("g")
            elif modePref == 'a':
                self.mode.set("a")
            elif modePref == 'b':
                self.mode.set("b")
            elif modePref == 'n':
                self.mode.set("n")
            elif modePref == 'ac':
                self.mode.set("ac")
            elif modePref == 'ax':
                self.mode.set("ax")
            elif modePref == 'be':
                self.mode.set("be")
            else:
                self.mode.set("g")
        else:
            self.mode.set("g")
        rowCount += 1

        # Field for signal range
        Label(self.leftfieldFrame, text="Signal Range:").grid(row=rowCount, sticky=E)
        self.rangeEntry = Entry(self.leftfieldFrame)
        self.rangeEntry.grid(row=rowCount, column=1)
        self.rangeEntry.insert(0, self.prefValues['range'])
        rowCount += 1

        # Selection of ap type
        Label(self.leftfieldFrame, text="AP Type:").grid(row=rowCount, sticky=E)
        self.apType = StringVar(self.leftfieldFrame)
        self.apTypeMenu = OptionMenu(self.leftfieldFrame, self.apType, "Default", "Open vSwitch Kernel Mode",
                                     "Userspace", "Userspace inNamespace")
        self.apTypeMenu.grid(row=rowCount, column=1, sticky=W)
        if 'apType' in self.prefValues:
            apTypePref = self.prefValues['apType']
            if apTypePref == 'userns':
                self.apType.set("Userspace inNamespace")
            elif apTypePref == 'user':
                self.apType.set("Userspace")
            elif apTypePref == 'ovs':
                self.apType.set("Open vSwitch Kernel Mode")
            else:
                self.apType.set("Default")
        else:
            self.apType.set("Default")
        rowCount += 1

        # Field for DPID
        Label(self.leftfieldFrame, text="DPID:").grid(row=rowCount, sticky=E)
        self.dpidEntry = Entry(self.leftfieldFrame)
        self.dpidEntry.grid(row=rowCount, column=1)
        if 'dpid' in self.prefValues:
            self.dpidEntry.insert(0, self.prefValues['dpid'])
        rowCount += 1

        # Field for Netflow
        Label(self.leftfieldFrame, text="Enable NetFlow:").grid(row=rowCount, sticky=E)
        self.nflow = IntVar()
        self.nflowButton = Checkbutton(self.leftfieldFrame, variable=self.nflow)
        self.nflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'netflow' in self.prefValues:
            if self.prefValues['netflow'] == '0':
                self.nflowButton.deselect()
            else:
                self.nflowButton.select()
        else:
            self.nflowButton.deselect()
        rowCount += 1

        # Field for sflow
        Label(self.leftfieldFrame, text="Enable sFlow:").grid(row=rowCount, sticky=E)
        self.sflow = IntVar()
        self.sflowButton = Checkbutton(self.leftfieldFrame, variable=self.sflow)
        self.sflowButton.grid(row=rowCount, column=1, sticky=W)
        if 'sflow' in self.prefValues:
            if self.prefValues['sflow'] == '0':
                self.sflowButton.deselect()
            else:
                self.sflowButton.select()
        else:
            self.sflowButton.deselect()
        rowCount += 1

        # Field for Switch IP
        Label(self.leftfieldFrame, text="IP Address:").grid(row=rowCount, sticky=E)
        self.ipEntry = Entry(self.leftfieldFrame)
        self.ipEntry.grid(row=rowCount, column=1)
        if 'apIP' in self.prefValues:
            self.ipEntry.insert(0, self.prefValues['apIP'])
        rowCount += 1

        # Field for DPCTL port
        Label(self.leftfieldFrame, text="DPCTL port:").grid(row=rowCount, sticky=E)
        self.dpctlEntry = Entry(self.leftfieldFrame)
        self.dpctlEntry.grid(row=rowCount, column=1)
        if 'dpctl' in self.prefValues:
            self.dpctlEntry.insert(0, self.prefValues['dpctl'])
        rowCount += 1

        # External Interfaces
        Label(self.rightfieldFrame, text="External Interface:").grid(row=0, sticky=E)
        self.b = Button(self.rightfieldFrame, text='Add', command=self.addInterface)
        self.b.grid(row=0, column=1)

        self.interfaceFrame = VerticalScrolledTable(self.rightfieldFrame, rows=0, columns=1,
                                                    title='External Interfaces')
        self.interfaceFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.tableFrame = self.interfaceFrame.interior

        # Add defined interfaces
        for externalInterface in externalInterfaces:
            self.tableFrame.addRow(value=[externalInterface])

        self.commandFrame = Frame(self.propFrame)
        self.commandFrame.grid(row=1, column=0, sticky='nswe', columnspan=2)
        self.commandFrame.columnconfigure(1, weight=1)
        # Start command
        Label(self.commandFrame, text="Start Command:").grid(row=0, column=0, sticky=W)
        self.startEntry = Entry(self.commandFrame)
        self.startEntry.grid(row=0, column=1, sticky='nsew')
        if 'startCommand' in self.prefValues:
            self.startEntry.insert(0, str(self.prefValues['startCommand']))
        # Stop command
        Label(self.commandFrame, text="Stop Command:").grid(row=1, column=0, sticky=W)
        self.stopEntry = Entry(self.commandFrame)
        self.stopEntry.grid(row=1, column=1, sticky='nsew')
        if 'stopCommand' in self.prefValues:
            self.stopEntry.insert(0, str(self.prefValues['stopCommand']))

        rowCount = 0
        # Selection of authentication
        Label(self.authFrame, text="Authentication:").grid(row=rowCount, sticky=E)
        self.authentication = StringVar(self.authFrame)
        self.authenticationMenu = OptionMenu(self.authFrame,
                                             self.authentication, "none", "WEP",
                                             "WPA", "WPA2", "8021x")
        self.authenticationMenu.grid(row=rowCount, column=1, sticky=W)
        if 'authentication' in self.prefValues:
            authPref = self.prefValues['authentication']
            if authPref == 'WEP':
                self.authentication.set("WEP")
            elif authPref == 'WPA':
                self.authentication.set("WPA")
            elif authPref == 'WPA2':
                self.authentication.set("WPA2")
            elif authPref == '8021x':
                self.authentication.set("8021x")
            else:
                self.authentication.set("none")
        else:
            self.authentication.set("none")
        rowCount += 1

        # Field for passwd
        Label(self.authFrame, text="Password:").grid(row=rowCount, sticky=E)
        self.passwdEntry = Entry(self.authFrame)
        self.passwdEntry.grid(row=rowCount, column=1)
        self.passwdEntry.insert(0, self.prefValues['passwd'])
        rowCount += 1

    def addInterface(self):
        self.tableFrame.addRow()

    def defaultDpid(self, name):
        """Derive dpid from switch name, s1 -> 1"""
        assert self  # satisfy pylint and allow contextual override
        try:
            dpid = int(re.findall(r'\d+', name)[0])
            dpid = hex(dpid)[2:]
            return dpid
        except IndexError:
            return None
            # raise Exception( 'Unable to derive default datapath ID - '
            #                 'please either specify a dpid or use a '
            #                 'canonical switch name such as s23.' )

    def apply(self):
        externalInterfaces = []
        for row in range(self.tableFrame.rows):
            # debug( 'Interface is ' + self.tableFrame.get(row, 0), '\n' )
            if len(self.tableFrame.get(row, 0)) > 0:
                externalInterfaces.append(self.tableFrame.get(row, 0))

        dpid = self.dpidEntry.get()
        if (self.defaultDpid(self.hostnameEntry.get()) is None
                and len(dpid) == 0):
            messagebox.showerror(title="Error",
                                 message='Unable to derive default datapath ID - '
                                         'please either specify a DPID or use a '
                                         'canonical switch name such as s23.')

        results = {'externalInterfaces': externalInterfaces,
                   'hostname': self.hostnameEntry.get(),
                   'dpid': dpid,
                   'startCommand': self.startEntry.get(),
                   'stopCommand': self.stopEntry.get(),
                   'sflow': str(self.sflow.get()),
                   'netflow': str(self.nflow.get()),
                   'dpctl': self.dpctlEntry.get(),
                   'apIP': self.ipEntry.get()}
        results['ssid'] = str(self.ssidEntry.get())
        results['channel'] = str(self.channelEntry.get())
        results['range'] = str(self.rangeEntry.get())
        results['wlans'] = self.wlansEntry.get()
        results['mode'] = str(self.mode.get())
        results['authentication'] = self.authentication.get()
        results['passwd'] = str(self.passwdEntry.get())
        ap = self.apType.get()
        if ap == 'Userspace inNamespace':
            results['apType'] = 'userns'
        elif ap == 'Userspace':
            results['apType'] = 'user'
        elif ap == 'Open vSwitch Kernel Mode':
            results['apType'] = 'ovs'
        else:
            results['apType'] = 'default'
        self.result = results


class VerticalScrolledTable(LabelFrame):
    """A pure Tkinter scrollable frame that actually works!

    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling

    """

    def __init__(self, parent, rows=2, columns=2, title=None, *args, **kw):
        LabelFrame.__init__(self, parent, text=title, padx=5, pady=5, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        canvas = Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=vscrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = TableFrame(canvas, rows=rows, columns=columns)
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(_event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(_event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        canvas.bind('<Configure>', _configure_canvas)

        return


class TableFrame(Frame):
    def __init__(self, parent, rows=2, columns=2):

        Frame.__init__(self, parent, background="black")
        self._widgets = []
        self.rows = rows
        self.columns = columns
        for row in range(rows):
            current_row = []
            for column in range(columns):
                label = Entry(self, borderwidth=0)
                label.grid(row=row, column=column, sticky="wens", padx=1, pady=1)
                current_row.append(label)
            self._widgets.append(current_row)

    def set(self, row, column, value):
        widget = self._widgets[row][column]
        widget.insert(0, value)

    def get(self, row, column):
        widget = self._widgets[row][column]
        return widget.get()

    def addRow(self, value=None, readonly=False):
        # debug( "Adding row " + str(self.rows +1), '\n' )
        current_row = []
        for column in range(self.columns):
            label = Entry(self, borderwidth=0)
            label.grid(row=self.rows, column=column, sticky="wens", padx=1, pady=1)
            if value is not None:
                label.insert(0, value[column])
            if readonly == True:
                label.configure(state='readonly')
            current_row.append(label)
        self._widgets.append(current_row)
        self.update_idletasks()
        self.rows += 1


class LinkDialog(simpledialog.Dialog):

    def __init__(self, parent, title, linkDefaults, links, src, dest):

        self.linkValues = linkDefaults
        self.links = links
        self.src = src
        self.dest = dest
        simpledialog.Dialog.__init__(self, parent, title)

    def body(self, master):
        if 'link' not in self.linkValues:
            self.linkValues['channel'] = '1'
        if 'ssid' not in self.linkValues:
            self.linkValues['ssid'] = 'new-ssid'
        if 'mode' not in self.linkValues:
            self.linkValues['mode'] = 'g'

        rowCount = 0
        Label(master, text="Connection:").grid(row=rowCount, sticky=E)
        connectionOpt = None
        if 'connection' in self.linkValues:
            connectionOpt = self.linkValues['connection']
        self.e1 = StringVar(master)
        self.opt1 = OptionMenu(master, self.e1, "wired", "adhoc", "mesh", "wifi-direct")
        self.opt1.grid(row=rowCount, column=1, sticky=W)
        if connectionOpt:
            if self.linkValues['connection'] == 'adhoc':
                self.e1.set("adhoc")
            elif self.linkValues['connection'] == 'wifi-direct':
                self.e1.set("wifi-direct")
            elif self.linkValues['connection'] == 'mesh':
                self.e1.set("mesh")
            else:
                self.e1.set("wired")
        else:
            self.e1.set("wired")

        rowCount += 1
        Label(master, text="SSID:").grid(row=rowCount, sticky=E)
        self.e2 = Entry(master)
        self.e2.grid(row=rowCount, column=1)
        self.e2.insert(0, str(self.linkValues['ssid']))

        rowCount += 1
        Label(master, text="Channel:").grid(row=rowCount, sticky=E)
        self.e3 = Entry(master)
        self.e3.grid(row=rowCount, column=1)
        self.e3.insert(0, str(self.linkValues['channel']))

        rowCount += 1
        Label(master, text="Mode:").grid(row=rowCount, sticky=E)
        modeOpt = None
        if 'mode' in self.linkValues:
            modeOpt = self.linkValues['mode']
        self.e4 = StringVar(master)
        self.opt1 = OptionMenu(master, self.e4, "a", "b", "g", "n", "ac", "ax", "be")
        self.opt1.grid(row=rowCount, column=1, sticky=W)
        if modeOpt:
            if self.linkValues['mode'] == 'a':
                self.e4.set("a")
            elif self.linkValues['mode'] == 'b':
                self.e4.set("b")
            elif self.linkValues['mode'] == 'g':
                self.e4.set("g")
            elif self.linkValues['mode'] == 'n':
                self.e4.set("n")
            elif self.linkValues['mode'] == 'ac':
                self.e4.set("ac")
            elif self.linkValues['mode'] == 'ax':
                self.e4.set("ax")
            elif self.linkValues['mode'] == 'be':
                self.e4.set("be")

        rowCount += 1
        Label(master, text="Bandwidth:").grid(row=rowCount, sticky=E)
        self.e5 = Entry(master)
        self.e5.grid(row=rowCount, column=1)
        Label(master, text="Mbit").grid(row=rowCount, column=2, sticky=W)
        if 'bw' in self.linkValues:
            self.e5.insert(0, str(self.linkValues['bw']))

        rowCount += 1
        Label(master, text="Delay:").grid(row=rowCount, sticky=E)
        self.e6 = Entry(master)
        self.e6.grid(row=rowCount, column=1)
        if 'delay' in self.linkValues:
            self.e6.insert(0, self.linkValues['delay'])

        rowCount += 1
        Label(master, text="Loss:").grid(row=rowCount, sticky=E)
        self.e7 = Entry(master)
        self.e7.grid(row=rowCount, column=1)
        Label(master, text="%").grid(row=rowCount, column=2, sticky=W)
        if 'loss' in self.linkValues:
            self.e7.insert(0, str(self.linkValues['loss']))

        rowCount += 1
        Label(master, text="Max Queue size:").grid(row=rowCount, sticky=E)
        self.e8 = Entry(master)
        self.e8.grid(row=rowCount, column=1)
        if 'max_queue_size' in self.linkValues:
            self.e8.insert(0, str(self.linkValues['max_queue_size']))

        rowCount += 1
        Label(master, text="Jitter:").grid(row=rowCount, sticky=E)
        self.e9 = Entry(master)
        self.e9.grid(row=rowCount, column=1)
        if 'jitter' in self.linkValues:
            self.e9.insert(0, self.linkValues['jitter'])

        rowCount += 1
        Label(master, text="Speedup:").grid(row=rowCount, sticky=E)
        self.e10 = Entry(master)
        self.e10.grid(row=rowCount, column=1)
        if 'speedup' in self.linkValues:
            self.e10.insert(0, str(self.linkValues['speedup']))

        if 'wlans' in self.src:
            rowCount += 1
            Label(master, text="Source:").grid(row=rowCount, sticky=E)
            srcOpt = None
            if 'src' in self.links:
                srcOpt = self.links['src']['text']
            wlans = []
            wlans.append('default')
            for wlan in range(int(self.src['wlans'])):
                wlan_ = wlan
                wlans.append('%s-wlan%s' % (srcOpt, wlan_))
            self.e11 = StringVar(master)
            self.opt2 = OptionMenu(master, self.e11, *tuple(wlans))
            self.opt2.grid(row=rowCount, column=1, sticky=W)
            if srcOpt and 'src' in self.linkValues:
                for wlan in wlans:
                    if self.linkValues['src'] == wlan:
                        self.e11.set(wlan)
            else:
                self.e11.set('default')
        else:
            self.e11 = ''

        if 'wlans' in self.dest:
            rowCount += 1
            Label(master, text="Destination:").grid(row=rowCount, sticky=E)
            destOpt = None
            if 'dest' in self.links:
                destOpt = self.links['dest']['text']
            wlans = []
            wlans.append('default')
            for wlan in range(int(self.dest['wlans'])):
                if 'ap' in destOpt:
                    wlan_ = wlan + 1
                else:
                    wlan_ = wlan
                wlans.append('%s-wlan%s' % (destOpt, wlan_))
            self.e12 = StringVar(master)
            self.opt3 = OptionMenu(master, self.e12, *tuple(wlans))
            self.opt3.grid(row=rowCount, column=1, sticky=W)
            if destOpt and 'dest' in self.linkValues:
                for wlan in wlans:
                    if self.linkValues['dest'] == wlan:
                        self.e12.set(wlan)
            else:
                self.e12.set('default')
        else:
            self.e12 = ''

        return self.e2  # initial focus

    def apply(self):
        self.result = {}
        if len(self.e1.get()) > 0:
            self.result['connection'] = (self.e1.get())
        if len(self.e2.get()) > 0:
            self.result['ssid'] = (self.e2.get())
        if len(self.e3.get()) > 0:
            self.result['channel'] = (self.e3.get())
        if len(self.e4.get()) > 0:
            self.result['mode'] = (self.e4.get())
        if len(self.e5.get()) > 0:
            self.result['bw'] = int(self.e5.get())
        if len(self.e6.get()) > 0:
            self.result['delay'] = self.e6.get()
        if len(self.e7.get()) > 0:
            self.result['loss'] = int(self.e7.get())
        if len(self.e8.get()) > 0:
            self.result['max_queue_size'] = int(self.e8.get())
        if len(self.e9.get()) > 0:
            self.result['jitter'] = self.e9.get()
        if len(self.e10.get()) > 0:
            self.result['speedup'] = int(self.e10.get())
        if self.e11 != '' and len(self.e11.get()) > 0:
            self.result['src'] = self.e11.get()
        if self.e12 != '' and len(self.e12.get()) > 0:
            self.result['dest'] = self.e12.get()


class ControllerDialog(simpledialog.Dialog):

    def __init__(self, parent, title, ctrlrDefaults=None):

        if ctrlrDefaults:
            self.ctrlrValues = ctrlrDefaults

        simpledialog.Dialog.__init__(self, parent, title)

    def body(self, master):

        self.var = StringVar(master)
        self.protcolvar = StringVar(master)

        rowCount = 0
        # Field for Hostname
        Label(master, text="Name:").grid(row=rowCount, sticky=E)
        self.hostnameEntry = Entry(master)
        self.hostnameEntry.grid(row=rowCount, column=1)
        self.hostnameEntry.insert(0, self.ctrlrValues['hostname'])
        rowCount += 1

        # Field for Remove Controller Port
        Label(master, text="Controller Port:").grid(row=rowCount, sticky=E)
        self.e2 = Entry(master)
        self.e2.grid(row=rowCount, column=1)
        self.e2.insert(0, self.ctrlrValues['remotePort'])
        rowCount += 1

        # Field for Controller Type
        Label(master, text="Controller Type:").grid(row=rowCount, sticky=E)
        controllerType = self.ctrlrValues['controllerType']
        self.o1 = OptionMenu(master, self.var, "Remote Controller", "In-Band Controller", "OpenFlow Reference",
                             "OVS Controller")
        self.o1.grid(row=rowCount, column=1, sticky=W)
        if controllerType == 'ref':
            self.var.set("OpenFlow Reference")
        elif controllerType == 'inband':
            self.var.set("In-Band Controller")
        elif controllerType == 'remote':
            self.var.set("Remote Controller")
        else:
            self.var.set("OVS Controller")
        rowCount += 1

        # Field for Controller Protcol
        Label(master, text="Protocol:").grid(row=rowCount, sticky=E)
        if 'controllerProtocol' in self.ctrlrValues:
            controllerProtocol = self.ctrlrValues['controllerProtocol']
        else:
            controllerProtocol = 'tcp'
        self.protcol = OptionMenu(master, self.protcolvar, "TCP", "SSL")
        self.protcol.grid(row=rowCount, column=1, sticky=W)
        if controllerProtocol == 'ssl':
            self.protcolvar.set("SSL")
        else:
            self.protcolvar.set("TCP")
        rowCount += 1

        # Field for Remove Controller IP
        remoteFrame = LabelFrame(master, text='Remote/In-Band Controller', padx=5, pady=5)
        remoteFrame.grid(row=rowCount, column=0, columnspan=2, sticky=W)

        Label(remoteFrame, text="IP Address:").grid(row=0, sticky=E)
        self.e1 = Entry(remoteFrame)
        self.e1.grid(row=0, column=1)
        self.e1.insert(0, self.ctrlrValues['remoteIP'])
        rowCount += 1

        return self.hostnameEntry  # initial focus

    def apply(self):
        self.result = {'hostname': self.hostnameEntry.get(),
                       'remoteIP': self.e1.get(),
                       'remotePort': int(self.e2.get())}

        controllerType = self.var.get()
        if controllerType == 'Remote Controller':
            self.result['controllerType'] = 'remote'
        elif controllerType == 'In-Band Controller':
            self.result['controllerType'] = 'inband'
        elif controllerType == 'OpenFlow Reference':
            self.result['controllerType'] = 'ref'
        else:
            self.result['controllerType'] = 'ovsc'
        controllerProtocol = self.protcolvar.get()
        if controllerProtocol == 'SSL':
            self.result['controllerProtocol'] = 'ssl'
        else:
            self.result['controllerProtocol'] = 'tcp'


class ToolTip(object):

    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        """Display text in tooltip window"""
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 27
        y = y + cy + self.widget.winfo_rooty() + 27
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(tw, text=self.text, justify=LEFT,
                      background="#ffffe0", relief=SOLID, borderwidth=1,
                      font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class MiniEdit(Frame):
    """A simple network editor for Wmnet."""

    def __init__(self, parent=None, cheight=600, cwidth=1000):

        self.defaultIpBase = '10.0.0.0/8'

        self.nflowDefaults = {'nflowTarget': '',
                              'nflowTimeout': '600',
                              'nflowAddId': '0'}
        self.sflowDefaults = {'sflowTarget': '',
                              'sflowSampling': '400',
                              'sflowHeader': '128',
                              'sflowPolling': '30'}

        self.appPrefs = {
            "ipBase": self.defaultIpBase,
            "startCLI": "1",
            "enableWmediumd": "1",
            "terminalType": 'xterm',
            "switchType": 'ovs',
            "apType": 'ovs',
            "authentication": 'none',
            "passwd": '',
            "mode": 'g',
            "dpctl": '',
            'sflow': self.sflowDefaults,
            'netflow': self.nflowDefaults,
            'openFlowVersions': {'ovsOf10': '1',
                                 'ovsOf11': '0',
                                 'ovsOf12': '0',
                                 'ovsOf13': '0'}
        }

        Frame.__init__(self, parent)
        self.action = None
        self.appName = 'MN-Edit'
        self.fixedFont = font.Font(family="DejaVu Sans Mono", size="12")

        # Style
        self.font = ('Geneva', 9)
        self.smallFont = ('Geneva', 7)
        self.bg = 'white'

        # Title
        self.top = self.winfo_toplevel()
        self.top.title(self.appName)

        # Menu bar
        self.createMenubar()

        # Editing canvas
        self.cheight, self.cwidth = cheight, cwidth
        self.cframe, self.canvas = self.createCanvas()

        # Toolbar
        self.controllers = {}

        # Toolbar
        self.images = miniEditImages()
        self.buttons = {}
        self.active = None
        self.tools = ('Select', 'Host', 'Station', 'Phone', 'Switch', 'AP',
                      'LegacySwitch', 'LegacyRouter', 'NetLink', 'Controller', 'WLC')
        self.customColors = {'Switch': 'darkGreen', 'Host': 'blue'}
        self.toolbar = self.createToolbar()

        # Layout
        self.toolbar.grid(column=0, row=0, sticky='nsew')
        self.cframe.grid(column=1, row=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.pack(expand=True, fill='both')

        # About box
        self.aboutBox = None

        # Initialize node data
        self.nodeBindings = self.createNodeBindings()
        self.nodePrefixes = {'LegacyRouter': 'r', 'LegacySwitch': 's', 'Switch': 's',
                             'AP': 'ap', 'Host': 'h', 'Station': 'sta', 'Phone': 'ph',
                             'Controller': 'c', 'WLC': 'wlc'}
        self.widgetToItem = {}
        self.itemToWidget = {}

        # Initialize link tool
        self.link = self.linkWidget = None

        # Selection support
        self.selection = None

        # Keyboard bindings
        self.bind('<Control-q>', lambda event: self.quit())
        self.bind('<KeyPress-Delete>', self.deleteSelection)
        self.bind('<KeyPress-BackSpace>', self.deleteSelection)
        self.focus()

        self.hostPopup = Menu(self.top, tearoff=0)
        self.hostPopup.add_command(label='Host Options', font=self.font)
        self.hostPopup.add_separator()
        self.hostPopup.add_command(label='Properties', font=self.font, command=self.hostDetails)

        self.hostRunPopup = Menu(self.top, tearoff=0)
        self.hostRunPopup.add_command(label='Host Options', font=self.font)
        self.hostRunPopup.add_separator()
        self.hostRunPopup.add_command(label='Terminal', font=self.font, command=self.xterm)

        self.stationPopup = Menu(self.top, tearoff=0)
        self.stationPopup.add_command(label='Station Options', font=self.font)
        self.stationPopup.add_separator()
        self.stationPopup.add_command(label='Properties', font=self.font, command=self.stationDetails)

        self.stationRunPopup = Menu(self.top, tearoff=0)
        self.stationRunPopup.add_command(label='Station Options', font=self.font)
        self.stationRunPopup.add_separator()
        self.stationRunPopup.add_command(label='Terminal', font=self.font, command=self.xterm)

        self.legacyRouterRunPopup = Menu(self.top, tearoff=0)
        self.legacyRouterRunPopup.add_command(label='Router Options', font=self.font)
        self.legacyRouterRunPopup.add_separator()
        self.legacyRouterRunPopup.add_command(label='Terminal', font=self.font, command=self.xterm)

        self.switchPopup = Menu(self.top, tearoff=0)
        self.switchPopup.add_command(label='Switch Options', font=self.font)
        self.switchPopup.add_separator()
        self.switchPopup.add_command(label='Properties', font=self.font, command=self.switchDetails)

        self.switchRunPopup = Menu(self.top, tearoff=0)
        self.switchRunPopup.add_command(label='Switch Options', font=self.font)
        self.switchRunPopup.add_separator()
        self.switchRunPopup.add_command(label='List bridge details', font=self.font, command=self.listBridge)

        self.wlcPopup = Menu(self.top, tearoff=0)
        self.wlcPopup.add_command(label='WLC Options', font=self.font)
        self.wlcPopup.add_separator()
        self.wlcPopup.add_command(label='Properties', font=self.font, command=self.wlcDetails)

        self.wlcRunPopup = Menu(self.top, tearoff=0)
        self.wlcRunPopup.add_command(label='WLC Options', font=self.font)
        self.wlcRunPopup.add_separator()
        self.wlcPopup.add_command(label='Properties', font=self.font, command=self.wlcDetails)
        self.wlcRunPopup.add_command(label='List bridge details', font=self.font, command=self.listBridge)

        self.apPopup = Menu(self.top, tearoff=0)
        self.apPopup.add_command(label='AP Options', font=self.font)
        self.apPopup.add_separator()
        self.apPopup.add_command(label='Properties', font=self.font, command=self.apDetails)

        self.apRunPopup = Menu(self.top, tearoff=0)
        self.apRunPopup.add_command(label='AP Options', font=self.font)
        self.apRunPopup.add_separator()
        self.apRunPopup.add_command(label='List bridge details', font=self.font, command=self.listBridge)
        self.apRunPopup.add_command(label='Properties', font=self.font, command=self.apDetails)

        self.linkPopup = Menu(self.top, tearoff=0)
        self.linkPopup.add_command(label='Link Options', font=self.font)
        self.linkPopup.add_separator()
        self.linkPopup.add_command(label='Properties', font=self.font, command=self.linkDetails)

        self.linkRunPopup = Menu(self.top, tearoff=0)
        self.linkRunPopup.add_command(label='Link Options', font=self.font)
        self.linkRunPopup.add_separator()
        self.linkRunPopup.add_command(label='Link Up', font=self.font, command=self.linkUp)
        self.linkRunPopup.add_command(label='Link Down', font=self.font, command=self.linkDown)

        self.controllerPopup = Menu(self.top, tearoff=0)
        self.controllerPopup.add_command(label='Controller Options', font=self.font)
        self.controllerPopup.add_separator()
        self.controllerPopup.add_command(label='Properties', font=self.font, command=self.controllerDetails)

        # Event handling initalization
        self.linkx = self.linky = self.linkItem = None
        self.lastSelection = None

        # Model initialization
        self.links = {}
        self.hostOpts = {}
        self.stationOpts = {}
        self.switchOpts = {}
        self.apOpts = {}
        self.phoneOpts = {}
        self.wlcOpts = {}
        self.range = {}
        self.hostCount = 0
        self.stationCount = 0
        self.phoneCount = 0
        self.switchCount = 0
        self.apCount = 0
        self.wlcCount = 0
        self.controllerCount = 0
        self.net = None

        # Close window gracefully
        Wm.wm_protocol(self.top, name='WM_DELETE_WINDOW', func=self.quit)

    def quit(self):
        """Stop our network, if any, then quit."""
        self.stop()
        Frame.quit(self)

    def createMenubar(self):
        """Create our menu bar."""

        font = self.font

        mbar = Menu(self.top, font=font)
        self.top.configure(menu=mbar)

        fileMenu = Menu(mbar, tearoff=False)
        mbar.add_cascade(label="File", font=font, menu=fileMenu)
        fileMenu.add_command(label="New", font=font, command=self.newTopology)
        fileMenu.add_command(label="Open", font=font, command=self.loadTopology)
        fileMenu.add_command(label="Save", font=font, command=self.saveTopology)
        fileMenu.add_command(label="Export Level 2 Script", font=font, command=self.exportScript)
        fileMenu.add_separator()
        fileMenu.add_command(label='Quit', command=self.quit, font=font)

        editMenu = Menu(mbar, tearoff=False)
        mbar.add_cascade(label="Edit", font=font, menu=editMenu)
        editMenu.add_command(label="Cut", font=font,
                             command=lambda: self.deleteSelection(None))
        editMenu.add_command(label="Preferences", font=font, command=self.prefDetails)

        runMenu = Menu(mbar, tearoff=False)
        mbar.add_cascade(label="Run", font=font, menu=runMenu)
        runMenu.add_command(label="Run", font=font, command=self.doRun)
        runMenu.add_command(label="Stop", font=font, command=self.doStop)
        fileMenu.add_separator()
        runMenu.add_command(label='Show OVS Summary', font=font, command=self.ovsShow)
        runMenu.add_command(label='Root Terminal', font=font, command=self.rootTerminal)

        # Application menu
        appMenu = Menu(mbar, tearoff=False)
        mbar.add_cascade(label="Help", font=font, menu=appMenu)
        appMenu.add_command(label='About Network Editor', command=self.about,
                            font=font)

    # Canvas

    def createCanvas(self):
        """Create and return our scrolling canvas frame."""
        f = Frame(self)

        canvas = Canvas(f, width=self.cwidth, height=self.cheight,
                        bg=self.bg)

        # Scroll bars
        xbar = Scrollbar(f, orient='horizontal', command=canvas.xview)
        ybar = Scrollbar(f, orient='vertical', command=canvas.yview)
        canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)

        # Resize box
        resize = Label(f, bg='white')

        # Layout
        canvas.grid(row=0, column=1, sticky='nsew')
        ybar.grid(row=0, column=2, sticky='ns')
        xbar.grid(row=1, column=1, sticky='ew')
        resize.grid(row=1, column=2, sticky='nsew')

        # Resize behavior
        f.rowconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.grid(row=0, column=0, sticky='nsew')
        f.bind('<Configure>', lambda event: self.updateScrollRegion())

        # Mouse bindings
        canvas.bind('<ButtonPress-1>', self.clickCanvas)
        canvas.bind('<B1-Motion>', self.dragCanvas)
        canvas.bind('<ButtonRelease-1>', self.releaseCanvas)

        return f, canvas

    def updateScrollRegion(self):
        """Update canvas scroll region to hold everything."""
        bbox = self.canvas.bbox('all')
        if bbox is not None:
            self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]))

    def canvasx(self, x_root):
        """Convert root x coordinate to canvas coordinate."""
        c = self.canvas
        return c.canvasx(x_root) - c.winfo_rootx()

    def canvasy(self, y_root):
        """Convert root y coordinate to canvas coordinate."""
        c = self.canvas
        return c.canvasy(y_root) - c.winfo_rooty()

    # Toolbar

    def activate(self, toolName):
        """Activate a tool and press its button."""
        # Adjust button appearance
        if self.active:
            self.buttons[self.active].configure(relief='raised')
        self.buttons[toolName].configure(relief='sunken')
        # Activate dynamic bindings
        self.active = toolName

    @staticmethod
    def createToolTip(widget, text):
        toolTip = ToolTip(widget)

        def enter(_event):
            toolTip.showtip(text)

        def leave(_event):
            toolTip.hidetip()

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def createToolbar(self):
        """Create and return our toolbar frame."""

        toolbar = Frame(self)

        # Tools
        for tool in self.tools:
            cmd = (lambda t=tool: self.activate(t))
            b = Button(toolbar, text=tool, font=self.smallFont, command=cmd)
            if tool in self.images:
                b.config(height=35, image=self.images[tool])
                self.createToolTip(b, str(tool))
                # b.config( compound='top' )
            b.pack(fill='x')
            self.buttons[tool] = b
        self.activate(self.tools[0])

        # Spacer
        Label(toolbar, text='').pack()

        # Commands
        for cmd, color in [('Stop', 'darkRed'), ('Run', 'darkGreen')]:
            doCmd = getattr(self, 'do' + cmd)
            b = Button(toolbar, text=cmd, font=self.smallFont,
                       fg=color, command=doCmd)
            b.pack(fill='x', side='bottom')

        return toolbar

    def doRun(self):
        """Run command."""
        self.activate('Select')
        for tool in self.tools:
            self.buttons[tool].config(state='disabled')
        self.start()

    def doStop(self):
        """Stop command."""
        self.stop()
        for tool in self.tools:
            self.buttons[tool].config(state='normal')

    def addNode(self, node, nodeNum, x, y, name=None):
        """Add a new node to our canvas."""
        if 'Switch' == node:
            self.switchCount += 1
        if 'AP' == node:
            self.apCount += 1
        if 'Host' == node:
            self.hostCount += 1
        if 'Station' == node:
            self.stationCount += 1
        if 'Controller' == node:
            self.controllerCount += 1
        if 'Phone' == node:
            self.phoneCount += 1
        if 'WLC' == node:
            self.wlcCount += 1
        if name is None:
            name = self.nodePrefixes[node] + nodeNum

        self.addNamedNode(node, name, x, y)

    def addNamedNode(self, node, name, x, y):
        """Add a new node to our canvas."""
        icon = self.nodeIcon(node, name)
        item = self.canvas.create_window(x, y, anchor='c', window=icon,
                                         tags=node)
        self.widgetToItem[icon] = item
        self.itemToWidget[item] = icon
        icon.links = {}

    def convertJsonUnicode(self, text):
        """Some part of Wmnet don't like Unicode"""
        unicode = str
        if isinstance(text, dict):
            return {self.convertJsonUnicode(key): self.convertJsonUnicode(value) for key, value in text.items()}
        elif isinstance(text, list):
            return [self.convertJsonUnicode(element) for element in text]
        elif isinstance(text, unicode):
            return text
        return text

    def loadTopology(self):
        """Load command."""
        c = self.canvas

        myFormats = [
            ('MN-WiFi Topology', '*.mn'),
            ('All Files', '*'),
        ]
        f = filedialog.askopenfile(filetypes=myFormats, mode='rb')
        if f is None: return
        self.newTopology()
        loadedTopology = self.convertJsonUnicode(json.load(f))

        # Load application preferences
        if 'application' in loadedTopology:
            self.appPrefs = self.appPrefs.copy()
            self.appPrefs.update(loadedTopology['application'])
            if "ovsOf10" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf10"] = '0'
            if "ovsOf11" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf11"] = '0'
            if "ovsOf12" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf12"] = '0'
            if "ovsOf13" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf13"] = '0'
            if "sflow" not in self.appPrefs:
                self.appPrefs["sflow"] = self.sflowDefaults
            if "netflow" not in self.appPrefs:
                self.appPrefs["netflow"] = self.nflowDefaults

        # Load controllers
        if 'controllers' in loadedTopology:
            if loadedTopology['version'] == '1':
                # This is old location of controller info
                hostname = 'c0'
                self.controllers = {}
                self.controllers[hostname] = loadedTopology['controllers']['c0']
                self.controllers[hostname]['hostname'] = hostname
                self.addNode('Controller', 0, float(30), float(30), name=hostname)
                icon = self.findWidgetByName(hostname)
                icon.bind('<Button-3>', self.do_controllerPopup)
            else:
                controllers = loadedTopology['controllers']
                for controller in controllers:
                    hostname = controller['opts']['hostname']
                    x = controller['x']
                    y = controller['y']
                    self.addNode('Controller', 0, float(x), float(y), name=hostname)
                    self.controllers[hostname] = controller['opts']
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_controllerPopup)

        # Load hosts
        if 'hosts' in loadedTopology:
            hosts = loadedTopology['hosts']
            for host in hosts:
                nodeNum = host['number']
                hostname = 'h' + nodeNum
                if 'hostname' in host['opts']:
                    hostname = host['opts']['hostname']
                else:
                    host['opts']['hostname'] = hostname
                if 'nodeNum' not in host['opts']:
                    host['opts']['nodeNum'] = int(nodeNum)
                x = host['x']
                y = host['y']
                self.addNode('Host', nodeNum, float(x), float(y), name=hostname)

                # Fix JSON converting tuple to list when saving
                if 'privateDirectory' in host['opts']:
                    newDirList = []
                    for privateDir in host['opts']['privateDirectory']:
                        if isinstance(privateDir, list):
                            newDirList.append((privateDir[0], privateDir[1]))
                        else:
                            newDirList.append(privateDir)
                    host['opts']['privateDirectory'] = newDirList
                self.hostOpts[hostname] = host['opts']
                icon = self.findWidgetByName(hostname)
                icon.bind('<Button-3>', self.do_hostPopup)

        # Load stations
        if 'stations' in loadedTopology:
            stations = loadedTopology['stations']
            for station in stations:
                nodeNum = station['number']
                hostname = 'sta' + nodeNum
                if 'hostname' in station['opts']:
                    hostname = station['opts']['hostname']
                else:
                    station['opts']['hostname'] = hostname
                if 'nodeNum' not in station['opts']:
                    station['opts']['nodeNum'] = int(nodeNum)
                if 'mode' not in station['opts']:
                    station['opts']['mode'] = 'g'
                x = float(station['x'])
                y = float(station['y'])
                self.addNode('Station', nodeNum, float(x), float(y), name=hostname)

                # Fix JSON converting tuple to list when saving
                if 'privateDirectory' in station['opts']:
                    newDirList = []
                    for privateDir in station['opts']['privateDirectory']:
                        if isinstance(privateDir, list):
                            newDirList.append((privateDir[0], privateDir[1]))
                        else:
                            newDirList.append(privateDir)
                    station['opts']['privateDirectory'] = newDirList
                self.stationOpts[hostname] = station['opts']
                icon = self.findWidgetByName(hostname)
                icon.bind('<Button-3>', self.do_stationPopup)

                name = self.stationOpts[hostname]
                range = self.getRange(name, 'Station')
                self.range[hostname] = self.createCircle(x, y, range, c)

        # Load switches
        if 'switches' in loadedTopology:
            switches = loadedTopology['switches']
            for switch in switches:
                nodeNum = switch['number']
                hostname = 's' + nodeNum
                if 'controllers' not in switch['opts']:
                    switch['opts']['controllers'] = []
                if 'switchType' not in switch['opts']:
                    switch['opts']['switchType'] = 'default'
                if 'hostname' in switch['opts']:
                    hostname = switch['opts']['hostname']
                else:
                    switch['opts']['hostname'] = hostname
                if 'nodeNum' not in switch['opts']:
                    switch['opts']['nodeNum'] = int(nodeNum)
                x = switch['x']
                y = switch['y']
                if switch['opts']['switchType'] == "legacyRouter":
                    self.addNode('LegacyRouter', nodeNum, float(x), float(y), name=hostname)
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_legacyRouterPopup)
                elif switch['opts']['switchType'] == "legacySwitch":
                    self.addNode('LegacySwitch', nodeNum, float(x), float(y), name=hostname)
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_legacySwitchPopup)
                else:
                    self.addNode('Switch', nodeNum, float(x), float(y), name=hostname)
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_switchPopup)
                self.switchOpts[hostname] = switch['opts']

                # create links to controllers
                if int(loadedTopology['version']) > 1:
                    controllers = self.switchOpts[hostname]['controllers']
                    for controller in controllers:
                        dest = self.findWidgetByName(controller)
                        dx, dy = self.canvas.coords(self.widgetToItem[dest])
                        self.link = self.canvas.create_line(float(x),
                                                            float(y),
                                                            dx,
                                                            dy,
                                                            width=4,
                                                            fill='red',
                                                            dash=(6, 4, 2, 4),
                                                            tag='link')
                        c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                        self.addLink(icon, dest, linktype='control')
                        self.createControlLinkBindings()
                        self.link = self.linkWidget = None
                else:
                    dest = self.findWidgetByName('c0')
                    dx, dy = self.canvas.coords(self.widgetToItem[dest])
                    self.link = self.canvas.create_line(float(x),
                                                        float(y),
                                                        dx,
                                                        dy,
                                                        width=4,
                                                        fill='red',
                                                        dash=(6, 4, 2, 4),
                                                        tag='link')
                    c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                    self.addLink(icon, dest, linktype='control')
                    self.createControlLinkBindings()
                    self.link = self.linkWidget = None

        # Load aps
        if 'aps' in loadedTopology:
            aps = loadedTopology['aps']
            for ap in aps:
                nodeNum = ap['number']
                hostname = 'ap' + nodeNum
                ssid = hostname + '-ssid'
                if 'ssid' not in ap['opts']:
                    ap['opts']['ssid'] = ssid
                if 'channel' not in ap['opts']:
                    ap['opts']['channel'] = 1
                if 'controllers' not in ap['opts']:
                    ap['opts']['controllers'] = []
                if 'apType' not in ap['opts']:
                    ap['opts']['apType'] = 'default'
                if 'authentication' not in ap['opts']:
                    ap['opts']['authentication'] = 'none'
                if 'passwd' not in ap['opts']:
                    ap['opts']['passwd'] = ''
                if 'mode' not in ap['opts']:
                    ap['opts']['mode'] = 'g'
                if 'range' not in ap['opts']:
                    ap['opts']['range'] = 'default'
                if 'wlans' not in ap['opts']:
                    ap['opts']['wlans'] = 1
                if 'ap' in ap['opts']:
                    hostname = ap['opts']['hostname']
                else:
                    ap['opts']['hostname'] = hostname
                if 'nodeNum' not in ap['opts']:
                    ap['opts']['nodeNum'] = int(nodeNum)
                x = float(ap['x'])
                y = float(ap['y'])
                if ap['opts']['apType'] == "legacyAP":
                    self.addNode('LegacyAP', nodeNum, float(x), float(y), name=hostname)
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_legacyAPPopup)
                else:
                    self.addNode('AP', nodeNum, float(x), float(y), name=hostname)
                    icon = self.findWidgetByName(hostname)
                    icon.bind('<Button-3>', self.do_apPopup)
                self.apOpts[hostname] = ap['opts']

                name = self.apOpts[hostname]
                range = self.getRange(name, 'AP')
                self.range[hostname] = self.createCircle(x, y, range, c)

                # create links to controllers
                if int(loadedTopology['version']) > 1:
                    controllers = self.apOpts[hostname]['controllers']
                    for controller in controllers:
                        dest = self.findWidgetByName(controller)
                        dx, dy = self.canvas.coords(self.widgetToItem[dest])
                        self.link = self.canvas.create_line(float(x),
                                                            float(y),
                                                            dx,
                                                            dy,
                                                            width=4,
                                                            fill='red',
                                                            dash=(6, 4, 2, 4),
                                                            tag='link')
                        c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                        self.addLink(icon, dest, linktype='control')
                        self.createControlLinkBindings()
                        self.link = self.linkWidget = None
                else:
                    dest = self.findWidgetByName('c0')
                    dx, dy = self.canvas.coords(self.widgetToItem[dest])
                    self.link = self.canvas.create_line(float(x),
                                                        float(y),
                                                        dx,
                                                        dy,
                                                        width=4,
                                                        fill='red',
                                                        dash=(6, 4, 2, 4),
                                                        tag='link')
                    c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                    self.addLink(icon, dest, linktype='control')
                    self.createControlLinkBindings()
                    self.link = self.linkWidget = None

        # Load links
        if 'links' in loadedTopology:
            links = loadedTopology['links']
            for link in links:
                srcNode = link['src']
                src = self.findWidgetByName(srcNode)
                sx, sy = self.canvas.coords(self.widgetToItem[src])

                destNode = link['dest']
                dest = self.findWidgetByName(destNode)
                dx, dy = self.canvas.coords(self.widgetToItem[dest])

                self.link = self.canvas.create_line(sx, sy, dx, dy, width=4,
                                                    fill='blue', tag='link')
                c.itemconfig(self.link, tags=c.gettags(self.link) + ('data',))
                self.addLink(src, dest, linkopts=link['opts'])
                self.createDataLinkBindings()
                self.link = self.linkWidget = None

        f.close()

    def findWidgetByName(self, name):
        for widget in self.widgetToItem:
            if name == widget['text']:
                return widget

    def newTopology(self):
        """New command."""
        for widget in self.widgetToItem.keys():
            self.deleteItem(self.widgetToItem[widget])
        for range_ in self.range.keys():
            self.deleteItem(self.range[range_])
        self.hostCount = 0
        self.stationCount = 0
        self.switchCount = 0
        self.apCount = 0
        self.controllerCount = 0
        self.phoneCount = 0
        self.wlcCount = 0
        self.links = {}
        self.hostOpts = {}
        self.stationOpts = {}
        self.phoneOpts = {}
        self.switchOpts = {}
        self.apOpts = {}
        self.controllers = {}
        self.wlcOpts = {}
        self.appPrefs["ipBase"] = self.defaultIpBase

    def saveTopology(self):
        """Save command."""
        myFormats = [
            ('MN-Wifi Topology', '*.mn'),
            ('All Files', '*'),
        ]

        savingDictionary = {}
        fileName = filedialog.asksaveasfilename(filetypes=myFormats, title="Save the topology as...")
        if len(fileName) > 0:
            # Save Application preferences
            savingDictionary['version'] = '2'

            # Save Switches and Hosts
            hostsToSave = []
            stationsToSave = []
            switchesToSave = []
            apsToSave = []
            controllersToSave = []
            wlcsToSave = []
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                x1, y1 = self.canvas.coords(self.widgetToItem[widget])
                if 'Switch' in tags or 'LegacySwitch' in tags or 'LegacyRouter' in tags:
                    nodeNum = self.switchOpts[name]['nodeNum']
                    nodeToSave = {'number': str(nodeNum),
                                  'x': str(x1),
                                  'y': str(y1),
                                  'opts': self.switchOpts[name]}
                    switchesToSave.append(nodeToSave)
                elif 'AP' in tags:
                    nodeNum = self.apOpts[name]['nodeNum']
                    nodeToSave = {'number': str(nodeNum),
                                  'x': str(x1),
                                  'y': str(y1),
                                  'opts': self.apOpts[name]}
                    apsToSave.append(nodeToSave)
                elif 'Host' in tags:
                    nodeNum = self.hostOpts[name]['nodeNum']
                    nodeToSave = {'number': str(nodeNum),
                                  'x': str(x1),
                                  'y': str(y1),
                                  'opts': self.hostOpts[name]}
                    hostsToSave.append(nodeToSave)
                elif 'Station' in tags:
                    nodeNum = self.stationOpts[name]['nodeNum']
                    nodeToSave = {'number': str(nodeNum),
                                  'x': str(x1),
                                  'y': str(y1),
                                  'opts': self.stationOpts[name]}
                    stationsToSave.append(nodeToSave)
                elif 'Controller' in tags:
                    nodeToSave = {'x': str(x1),
                                  'y': str(y1),
                                  'opts': self.controllers[name]}
                    controllersToSave.append(nodeToSave)
                else:
                    raise Exception("Cannot create mystery node: " + name)
            savingDictionary['hosts'] = hostsToSave
            savingDictionary['stations'] = stationsToSave
            savingDictionary['switches'] = switchesToSave
            savingDictionary['aps'] = apsToSave
            savingDictionary['controllers'] = controllersToSave
            savingDictionary['wlcs'] = wlcsToSave

            # Save Links
            linksToSave = []
            for link in self.links.values():
                src = link['src']
                dst = link['dest']
                linkopts = link['linkOpts']

                srcName, dstName = src['text'], dst['text']
                linkToSave = {'src': srcName,
                              'dest': dstName,
                              'opts': linkopts}
                if link['type'] == 'data':
                    linksToSave.append(linkToSave)
            savingDictionary['links'] = linksToSave

            # Save Application preferences
            savingDictionary['application'] = self.appPrefs

            try:
                f = open(fileName, 'wb')
                f.write(json.dumps(savingDictionary, sort_keys=True, indent=4, separators=(',', ': ')).encode())
            # pylint: disable=broad-except
            except Exception as er:
                warn(er, '\n')
            # pylint: enable=broad-except
            finally:
                f.close()

    def exportScript(self):
        """Export command."""
        myFormats = [
            ('Wmnet Custom Topology', '*.py'),
            ('All Files', '*'),
        ]

        isWiFi = False
        controllerType_ = ''
        apType_ = ''
        switchType_ = ''
        hasSwitch = False
        hasAP = False
        hasController = False
        hasStation = False
        hasLegacyRouter = False
        hasLegacySwitch = False
        hasHost = False
        isCPU = False
        for widget in self.widgetToItem:
            tags = self.canvas.gettags(self.widgetToItem[widget])
            name = widget['text']
            if 'Station' in tags or 'AP' in tags:
                isWiFi = True
                hasAP = True
                hasStation = True
            if 'Controller' in tags:
                hasController = True
                opts = self.controllers[name]
                controllerType = opts['controllerType']
                if controllerType == 'ref':
                    if ' Controller' not in controllerType_:
                        controllerType_ += ' Controller,'
                elif controllerType == 'remote':
                    if ' RemoteController' not in controllerType_:
                        controllerType_ += ' RemoteController,'
            elif 'AP' in tags:
                opts = self.apOpts[name]
                apType = opts['apType']
                if apType == 'user':
                    if ' UserAP' not in apType_:
                        apType_ += ' UserAP,'
                elif apType == 'default':
                    if ' OVSKernelAP' not in apType_:
                        apType_ += ' OVSKernelAP,'
            elif 'Switch' in tags:
                hasSwitch = True
                opts = self.switchOpts[name]
                switchType = opts['switchType']
                if switchType == 'user':
                    if ' UserSwitch' not in switchType_:
                        switchType_ += ' UserSwitch,'
                elif switchType == 'default':
                    if ' OVSKernelSwitch' not in switchType_:
                        switchType_ += ' OVSKernelSwitch,'
            elif 'Host' in tags:
                hasHost = True
                opts = self.hostOpts[name]
                if 'cores' in opts or 'cpu' in opts:
                    isCPU = True
            elif 'LegacyRouter' in tags:
                hasLegacyRouter = True
            elif 'LegacySwitch' in tags:
                hasLegacySwitch = True

        links_ = ''
        sixLinks_ = ''
        for key, linkDetail in self.links.items():
            tags = self.canvas.gettags(key)
            if 'data' in tags:
                linkopts = linkDetail['linkOpts']
                if 'connection' in linkopts:
                    if 'adhoc' in linkopts['connection'] and ', adhoc' not in links_:
                        links_ += ', adhoc'
                    elif 'mesh' in linkopts['connection'] and ', mesh' not in links_:
                        links_ += ', mesh'
                    elif 'wifi-direct' in linkopts['connection'] and ', wifi-direct' not in links_:
                        links_ += ', wifiDirectLink'
                    elif '6lowpan' in linkopts['connection'] and 'sixLoWPANLink' not in sixLinks_:
                        sixLinks_ += ' sixLoWPANLink'

        fileName = filedialog.asksaveasfilename(filetypes=myFormats, title="Export the topology as...")
        if len(fileName) > 0:
            # debug( "Now saving under %s\n" % fileName )
            f = open(fileName, 'wb')

            f.write(b"#!/usr/bin/python\n")
            f.write(b"\n")
            if not isWiFi:
                f.write(b"from apns.net import Wmnet\n")
            args = ''
            if hasController:
                if not controllerType_:
                    controllerType_ = ' Controller'
                else:
                    controllerType_ = controllerType_[:-1]
                args += controllerType_
            if hasSwitch:
                if not switchType_:
                    switchType_ = ' OVSKernelSwitch'
                else:
                    switchType_ = switchType_[:-1]
                if args:
                    args += ',' + switchType_
                else:
                    args += switchType_
            if hasHost:
                if args:
                    args += ', '
                args += ' Host'
                if isCPU:
                    if args:
                        args += ', '
                    args += 'CPULimitedHost'
            if hasLegacyRouter:
                if args:
                    args += ', '
                args += ' Node'
            if hasLegacySwitch:
                if args:
                    args += ', '
                args += ' OVSKernelSwitch'

            if args:
                f.write(b"from apns.node import" + args.encode() + b"\n")

            if not isWiFi:
                f.write(b"from apns.cli import CLI\n")
                f.write(b"from apns.link import TCLink, Intf\n")
            f.write(b"from apns.log import setLogLevel, info\n")

            if isWiFi:
                f.write(b"from apns.net import Wmnet\n")
                args = b''
                if hasStation:
                    args += b' Station'
                if hasAP:
                    if not apType_:
                        apType_ = ' OVSKernelAP'
                    else:
                        apType_ = apType_[:-1]
                    if args:
                        args += b',' + apType_.encode()
                    else:
                        args += apType_.encode()
                if args:
                    f.write(b"from apns.node import" + args + b"\n")
                f.write(b"from apns.cli import CLI\n")
                if not links_:
                    links_ = ''
                f.write(b"from apns.link import wmediumd" + links_.encode() + b"\n")
                f.write(b"from apns.wmediumdConnector import interference\n")
            f.write(b"from subprocess import call\n")

            inBandCtrl = False
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])

                if 'Controller' in tags:
                    opts = self.controllers[name]
                    controllerType = opts['controllerType']
                    if controllerType == 'inband':
                        inBandCtrl = True

            if inBandCtrl:
                f.write(b"\n")
                f.write(b"class InbandController( RemoteController ):\n")
                f.write(b"\n")
                f.write(b"    def checkListening( self ):\n")
                f.write(b"        \"Overridden to do nothing.\"\n")
                f.write(b"        return\n")

            f.write(b"\n")
            f.write(b"\n")
            f.write(b"def myNetwork():\n")
            f.write(b"\n")
            if not isWiFi:
                f.write(b"    net = Wmnet(topo=None,\n")
            else:
                f.write(b"    net = Wmnet(topo=None,\n")
            if len(self.appPrefs['dpctl']) > 0:
                f.write(b"                       listenPort=" + self.appPrefs['dpctl'].encode() + b",\n")
            f.write(b"                       build=False,\n")
            if isWiFi:
                f.write(b"                       link=wmediumd,\n")
                f.write(b"                       wmediumd_mode=interference,\n")
            f.write(b"                       ipBase='" + self.appPrefs['ipBase'].encode() + b"')\n")
            f.write(b"\n")
            f.write(b"    info( '--- Adding SDN controller\\n' )\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])

                if 'Controller' in tags:
                    opts = self.controllers[name]
                    controllerType = opts['controllerType']
                    if 'controllerProtocol' in opts:
                        controllerProtocol = opts['controllerProtocol']
                    else:
                        controllerProtocol = b'tcp'
                    controllerIP = opts['remoteIP']
                    controllerPort = str(opts['remotePort'])

                    f.write(b"    " + name.encode() + b" = net.addController(name='" + name.encode() + b"',\n")

                    if controllerType == b'remote':
                        f.write(b"                           controller=RemoteController,\n")
                        f.write(b"                           ip='" + controllerIP.encode() + b"',\n")
                    elif controllerType == b'inband':
                        f.write(b"                           controller=InbandController,\n")
                        f.write(b"                           ip='" + controllerIP.encode() + b"',\n")
                    elif controllerType == b'ovsc':
                        f.write(b"                           controller=OVSController,\n")
                    else:
                        f.write(b"                           controller=Controller,\n")

                    f.write(b"                           protocol='" + controllerProtocol.encode() + b"',\n")
                    f.write(b"                           port=" + controllerPort.encode() + b")\n")
                    f.write(b"\n")

            # Save Switches and Hosts
            f.write(b"    info( '--- Add switches/APs\\n')\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                x1, y1 = self.canvas.coords(self.widgetToItem[widget])
                if 'LegacyRouter' in tags:
                    f.write(
                        b"    " + name.encode() + b" = net.addHost('" + name.encode() + b"', cls=Node, ip='0.0.0.0')\n")
                    f.write(b"    " + name.encode() + b".cmd('sysctl -w net.ipv4.ip_forward=1')\n")
                if 'LegacySwitch' in tags:
                    f.write(
                        b"    " + name.encode() + b"  = net.addSwitch('" + name.encode() + b"', cls=OVSKernelSwitch, failMode='standalone')\n")
                if 'Switch' in tags:
                    opts = self.switchOpts[name]
                    nodeNum = opts['nodeNum']
                    f.write(b"    " + name.encode() + b" = net.addSwitch('" + name.encode() + b"'")
                    if opts['switchType'] == 'default':
                        if self.appPrefs['switchType'] == 'user':
                            f.write(b", cls=UserSwitch")
                        elif self.appPrefs['switchType'] == 'userns':
                            f.write(b", cls=UserSwitch, inNamespace=True")
                        else:
                            f.write(b", cls=OVSKernelSwitch")
                    elif opts['switchType'] == 'user':
                        f.write(b", cls=UserSwitch")
                    elif opts['switchType'] == 'userns':
                        f.write(b", cls=UserSwitch, inNamespace=True")
                    else:
                        f.write(b", cls=OVSKernelSwitch")
                    if 'dpctl' in opts:
                        f.write(b", listenPort=" + opts['dpctl'].encode())
                    if 'dpid' in opts:
                        f.write(b", dpid='" + opts['dpid'].encode() + b"'")
                    f.write(b")\n")
                    if 'externalInterfaces' in opts:
                        for extInterface in opts['externalInterfaces']:
                            f.write(b"    Intf( '" + extInterface.encode() + b"', node=" + name.encode() + b" )\n")
                if 'AP' in tags:
                    opts = self.apOpts[name]
                    nodeNum = opts['nodeNum']
                    f.write(b"    " + name.encode() + b" = net.addAP('" + name.encode() + b"'")
                    if opts['apType'] == 'default':
                        if self.appPrefs['apType'] == 'user':
                            f.write(b", cls=UserAP")
                        elif self.appPrefs['apType'] == 'userns':
                            f.write(b", cls=UserAP, inNamespace=True")
                        else:
                            f.write(b", cls=OVSKernelAP")
                    elif opts['apType'] == 'user':
                        f.write(b", cls=UserAP")
                    elif opts['apType'] == 'userns':
                        f.write(b", cls=UserAP, inNamespace=True")
                    else:
                        f.write(b", cls=OVSKernelAP")
                    if 'dpctl' in opts:
                        f.write(b", listenPort=" + opts['dpctl'].encode())
                    if 'dpid' in opts:
                        f.write(b", dpid='" + opts['dpid'].encode() + b"'")
                    if 'ssid' in opts:
                        f.write(b", ssid='" + opts['ssid'].encode() + b"'")
                    if 'channel' in opts:
                        f.write(b",\n                             channel='" + opts['channel'].encode() + b"'")
                    if 'mode' in opts:
                        f.write(b", mode='" + opts['mode'].encode() + b"'")
                    if 'apIP' in opts and opts['apIP']:
                        f.write(b", ip='" + opts['apIP'].encode() + b"'")
                    if 'authentication' in opts and opts['authentication'] != 'none':
                        if opts['authentication'] == '8021x':
                            f.write(b", encrypt='wpa2', authmode='8021x'")
                        else:
                            f.write(b", encrypt='" + opts['authentication'].encode() +
                                    b"',\n                             passwd='" + opts['passwd'].encode() + b"'")
                    f.write(b", position='" + str(x1).encode() + b"," + str(y1).encode() + b",0'")
                    if opts['range'] != 'default':
                        f.write(b", range=" + str(opts['range']).encode() + b"")
                    f.write(b")\n")
                    if 'externalInterfaces' in opts:
                        for extInterface in opts['externalInterfaces']:
                            f.write(b"    Intf( '" + extInterface.encode() + b"', node=" + name.encode() + b" )\n")

            f.write(b"\n")
            f.write(b"    info( '--- Add hosts/stations\\n')\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                x1, y1 = self.canvas.coords(self.widgetToItem[widget])
                if 'Host' in tags:
                    opts = self.hostOpts[name]
                    ip = None
                    defaultRoute = None
                    if 'defaultRoute' in opts and len(opts['defaultRoute']) > 0:
                        defaultRoute = "'via " + opts['defaultRoute'] + "'"
                    else:
                        defaultRoute = 'None'
                    if 'ip' in opts and len(opts['ip']) > 0:
                        ip = opts['ip']
                    else:
                        nodeNum = self.hostOpts[name]['nodeNum']
                        ipBaseNum, prefixLen = netParse(self.appPrefs['ipBase'])
                        ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)

                    if 'cores' in opts or 'cpu' in opts:
                        f.write(
                            b"    " + name.encode() + b" = net.addHost('" + name.encode() + b"', cls=CPULimitedHost, ip='" + ip.encode() + b"', defaultRoute=" + defaultRoute.encode() + b")\n")
                        if 'cores' in opts:
                            f.write(b"    " + name.encode() + b".setCPUs(cores='" + opts['cores'].encode() + b"')\n")
                        if 'cpu' in opts:
                            f.write(
                                b"    " + name.encode() + b".setCPUFrac(f=" + str(opts['cpu']).encode() + b", sched='" +
                                opts['sched'].encode() + b"')\n")
                    else:
                        f.write(
                            b"    " + name.encode() + b" = net.addHost('" + name.encode() + b"', cls=Host, ip='" + ip.encode() + b"', defaultRoute=" + defaultRoute.encode() + b")\n")
                    if 'externalInterfaces' in opts:
                        for extInterface in opts['externalInterfaces']:
                            f.write(b"    Intf( '" + extInterface.encode() + b"', node=" + name.encode() + b" )\n")
                if 'Station' in tags:
                    opts = self.stationOpts[name]
                    ip = None
                    defaultRoute = None
                    wlans = opts['wlans']
                    wpans = opts['wpans']
                    if 'defaultRoute' in opts and len(opts['defaultRoute']) > 0:
                        defaultRoute = "'via " + opts['defaultRoute'] + "'"
                    else:
                        defaultRoute = 'None'
                    nodeNum = self.stationOpts[name]['nodeNum']
                    if 'ip' in opts and len(opts['ip']) > 0:
                        ip = opts['ip']
                    else:
                        ipBaseNum, prefixLen = netParse(self.appPrefs['ipBase'])
                        ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)
                    args = ''
                    if int(wlans) > 1:
                        args += ', wlans=%s' % wlans
                    if int(wpans) > 0:
                        args += ', sixlowpan=%s' % wpans
                        wpanip = ", wpan_ip='2001::%s/64'" % nodeNum
                        args += wpanip
                    if 'authentication' in opts and opts['authentication']:
                        args_ = ['wpa', 'wpa2', 'wep']
                        if opts['authentication'] in args_:
                            args += ", encrypt='%s'" % opts['authentication']
                    if 'passwd' in opts and opts['passwd']:
                        if opts['passwd'] != '':
                            args += ", passwd='%s'" % opts['passwd']
                    if 'user' in opts and opts['user']:
                        if opts['user'] != '':
                            args += ", radius_identity='%s'" % opts['user']
                    if 'defaultRoute' in opts:
                        args += ", defaultRoute='%s'" % defaultRoute
                    if opts['range'] != 'default':
                        args += ", range=%s" % opts['range']
                    if 'cores' in opts or 'cpu' in opts:
                        f.write(
                            b"    " + name.encode() + b" = net.addSta('" + name.encode() + b"', cls=CPULimitedHost, ip='" + ip.encode() + b"', defaultRoute=" + defaultRoute.encode() + b", position='" + str(
                                x1).encode() + b"," + str(y1).encode() + b",0'" + args.encode() + b")\n")
                        if 'cores' in opts:
                            f.write(b"    " + name.encode() + b".setCPUs(cores='" + opts['cores'].encode() + b"')\n")
                        if 'cpu' in opts:
                            f.write(
                                b"    " + name.encode() + b".setCPUFrac(f=" + str(opts['cpu']).encode() + b", sched='" +
                                opts['sched'].encode() + b"')\n")
                    else:
                        f.write(
                            b"    " + name.encode() + b" = net.addSta('" + name.encode() + b"', ip='" + ip.encode() + b"',\n                           position='" + str(
                                x1).encode() + b"," + str(y1).encode() + b",0'" + args.encode() + b")\n")
                    if 'externalInterfaces' in opts:
                        for extInterface in opts['externalInterfaces']:
                            f.write(b"    Intf( '" + extInterface.encode() + b"', node=" + name.encode() + b" )\n")
            f.write(b"\n")

            if isWiFi:
                f.write(b"    info(\"--- Configure propagation model\\n\")\n")
                f.write(b"    net.setPropagationModel(model=\"logDistance\", exp=3)\n")
                f.write(b"\n")

            # Save Links
            lowpan = []
            if self.links:
                f.write(b"    info( '--- Add links\\n')\n")
            for key, linkDetail in self.links.items():
                tags = self.canvas.gettags(key)
                if 'data' in tags:
                    optsExist = False
                    src = linkDetail['src']
                    dst = linkDetail['dest']
                    linkopts = linkDetail['linkOpts']
                    srcName, dstName = src['text'], dst['text']
                    bw = ''
                    # delay = ''
                    # loss = ''
                    # max_queue_size = ''
                    linkOpts = "{"
                    if 'bw' in linkopts:
                        bw = linkopts['bw']
                        linkOpts = linkOpts + "'bw':" + str(bw)
                        optsExist = True
                    if 'delay' in linkopts:
                        # delay =  linkopts['delay']
                        if optsExist:
                            linkOpts = linkOpts + ","
                        linkOpts = linkOpts + "'delay':'" + linkopts['delay'] + "'"
                        optsExist = True
                    if 'loss' in linkopts:
                        if optsExist:
                            linkOpts = linkOpts + ","
                        linkOpts = linkOpts + "'loss':" + str(linkopts['loss'])
                        optsExist = True
                    if 'max_queue_size' in linkopts:
                        if optsExist:
                            linkOpts = linkOpts + ","
                        linkOpts = linkOpts + "'max_queue_size':" + str(linkopts['max_queue_size'])
                        optsExist = True
                    if 'jitter' in linkopts:
                        if optsExist:
                            linkOpts = linkOpts + ","
                        linkOpts = linkOpts + "'jitter':'" + linkopts['jitter'] + "'"
                        optsExist = True
                    if 'speedup' in linkopts:
                        if optsExist:
                            linkOpts = linkOpts + ","
                        linkOpts = linkOpts + "'speedup':" + str(linkopts['speedup'])
                        optsExist = True

                    linkOpts = linkOpts + "}"
                    args_ = ['adhoc', 'mesh', 'wifiDirect']
                    if optsExist:
                        f.write(b"    " + srcName.encode() + dstName.encode() + b" = " + linkOpts.encode() + b"\n")
                    if 'connection' in linkopts and '6lowpan' in linkopts['connection']:
                        if srcName not in lowpan:
                            f.write(b"    net.addLink(" + srcName.encode() + b", cls=sixLoWPANLink, panid='0xbeef')\n")
                            lowpan.append(srcName)
                        if dstName not in lowpan:
                            f.write(b"    net.addLink(" + dstName.encode() + b", cls=sixLoWPANLink, panid='0xbeef')\n")
                            lowpan.append(dstName)
                    elif 'connection' in linkopts and linkopts['connection'] in args_:
                        nodes = []
                        nodes.append(srcName)
                        nodes.append(dstName)
                        for node in nodes:
                            f.write(b"    net.addLink(" + node.encode())
                            if 'adhoc' in linkopts['connection'] or 'mesh' in linkopts['connection']:
                                link = ", cls={}, ssid=\'{}\', mode=\'{}\', channel={}".format(linkopts['connection'],
                                                                                               linkopts['ssid'],
                                                                                               linkopts['mode'],
                                                                                               linkopts['channel'])
                                f.write(link.encode())
                            elif 'wifiDirect' in linkopts['connection']:
                                f.write(b", cls=wifiDirectLink")
                            intf = None

                            if 'src' in linkopts and nodes.index(node) == 0:
                                intf = linkopts['src']
                            elif 'dest' in linkopts and nodes.index(node) == 1:
                                intf = linkopts['dest']
                            if intf and intf != 'default':
                                f.write(b", intf=\'%s\'" % intf)
                            f.write(b")\n")
                    else:
                        f.write(b"    net.addLink(" + srcName.encode() + b", " + dstName.encode())
                        if optsExist:
                            f.write(b", cls=TCLink , **" + srcName.encode() + dstName.encode())
                        if ('connection' in linkopts and '6lowpan' not in linkopts['connection']) \
                                or 'connection' not in linkopts:
                            f.write(b")\n")
            if self.links:
                f.write(b"\n")
            if isWiFi:
                f.write(b"    net.plotGraph(max_x=1000, max_y=1000)\n")
                f.write(b"\n")

            f.write(b"    info( '--- Starting net\\n')\n")
            f.write(b"    net.build()\n")

            f.write(b"    info( '--- Starting controllers\\n')\n")
            f.write(b"    for controller in net.controllers:\n")
            f.write(b"        controller.start()\n")
            f.write(b"\n")

            f.write(b"    info( '--- Starting switches/APs\\n')\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Switch' in tags or 'LegacySwitch' in tags or 'AP' in tags:
                    if 'AP' in tags:
                        opts = self.apOpts[name]
                    else:
                        opts = self.switchOpts[name]
                    ctrlList = ",".join(opts['controllers'])
                    f.write(b"    net.get('" + name.encode() + b"').start([" + ctrlList.encode() + b"])\n")

            f.write(b"\n")

            f.write(b"    info( '--- Post configure nodes\\n')\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Switch' in tags:
                    opts = self.switchOpts[name]
                    if opts['switchType'] == 'default':
                        if self.appPrefs['switchType'] == 'user':
                            if 'switchIP' in opts:
                                if len(opts['switchIP']) > 0:
                                    f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b" " + opts[
                                        'switchIP'].encode() + b"')\n")
                        elif self.appPrefs['switchType'] == 'userns':
                            if 'switchIP' in opts:
                                if len(opts['switchIP']) > 0:
                                    f.write(b"    " + name.encode() + b".cmd('ifconfig lo " + opts[
                                        'switchIP'].encode() + b"')\n")
                        elif self.appPrefs['switchType'] == 'ovs':
                            if 'switchIP' in opts:
                                if len(opts['switchIP']) > 0:
                                    f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b" " + opts[
                                        'switchIP'].encode() + b"')\n")
                    elif opts['switchType'] == 'user':
                        if 'switchIP' in opts:
                            if len(opts['switchIP']) > 0:
                                f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b" " + opts[
                                    'switchIP'].encode() + b"')\n")
                    elif opts['switchType'] == 'userns':
                        if 'switchIP' in opts:
                            if len(opts['switchIP']) > 0:
                                f.write(b"    " + name.encode() + b".cmd('ifconfig lo " + opts[
                                    'switchIP'].encode() + b"')\n")
                    elif opts['switchType'] == 'ovs':
                        if 'switchIP' in opts:
                            if len(opts['switchIP']) > 0:
                                f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b" " + opts[
                                    'switchIP'].encode() + b"')\n")
                elif 'AP' in tags:
                    opts = self.apOpts[name]
                    if opts['apType'] == 'default' or opts['apType'] == 'ovs':
                        if 'apIP' in opts:
                            if len(opts['apIP']) > 0:
                                f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b" " + opts[
                                    'apIP'].encode() + b"')\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Host' in tags:
                    opts = self.hostOpts[name]
                    # Attach vlan interfaces
                    if 'vlanInterfaces' in opts:
                        for vlanInterface in opts['vlanInterfaces']:
                            f.write(b"    " + name.encode() + b".cmd('vconfig add " + name.encode() + b"-eth0 " +
                                    vlanInterface[1].encode() + b"')\n")
                            f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b"-eth0." +
                                    vlanInterface[1].encode() + b" " + vlanInterface[0].encode() + b"')\n")
                    # Run User Defined Start Command
                    if 'startCommand' in opts:
                        f.write(b"    " + name.encode() + b".cmdPrint('" + opts['startCommand'].encode() + b"')\n")
                elif 'Station' in tags:
                    opts = self.stationOpts[name]
                    # Attach vlan interfaces
                    if 'vlanInterfaces' in opts:
                        for vlanInterface in opts['vlanInterfaces']:
                            f.write(b"    " + name.encode() + b".cmd('vconfig add " + name.encode() + b"-wlan0 " +
                                    vlanInterface[1].encode() + b"')\n")
                            f.write(b"    " + name.encode() + b".cmd('ifconfig " + name.encode() + b"-wlan0." +
                                    vlanInterface[1].encode() + b" " + vlanInterface[0].encode() + b"')\n")
                    # Run User Defined Start Command
                    if 'startCommand' in opts:
                        f.write(b"    " + name.encode() + b".cmdPrint('" + opts['startCommand'].encode() + b"')\n")
                if 'Switch' in tags or 'AP' in tags:
                    if 'Switch' in tags:
                        opts = self.switchOpts[name]
                    else:
                        opts = self.apOpts[name]
                    # Run User Defined Start Command
                    if 'startCommand' in opts:
                        f.write(b"    " + name.encode() + b".cmdPrint('" + opts['startCommand'].encode() + b"')\n")

            # Configure NetFlow
            nflowValues = self.appPrefs['netflow']
            if len(nflowValues['nflowTarget']) > 0:
                nflowEnabled = False
                nflowSwitches = ''
                nflowAPs = ''
                for widget in self.widgetToItem:
                    name = widget['text']
                    tags = self.canvas.gettags(self.widgetToItem[widget])

                    if 'Switch' in tags:
                        opts = self.switchOpts[name]
                        if 'netflow' in opts:
                            if opts['netflow'] == '1':
                                nflowSwitches = nflowSwitches + ' -- set Bridge ' + name + ' netflow=@MiniEditNF'
                                nflowEnabled = True
                    elif 'AP' in tags:
                        opts = self.apOpts[name]
                        if 'netflow' in opts:
                            if opts['netflow'] == '1':
                                nflowAPs = nflowAPs + ' -- set Bridge ' + name + ' netflow=@MiniEditNF'
                                nflowEnabled = True
                if nflowEnabled:
                    nflowCmd = 'ovs-vsctl -- --id=@MiniEditNF create NetFlow ' + 'target=\\\"' + nflowValues[
                        'nflowTarget'] + '\\\" ' + 'active-timeout=' + nflowValues['nflowTimeout']
                    if nflowValues['nflowAddId'] == '1':
                        nflowCmd = nflowCmd + ' add_id_to_interface=true'
                    else:
                        nflowCmd = nflowCmd + ' add_id_to_interface=false'
                    f.write(b"    \n")
                    f.write(b"    call('" + nflowCmd.encode() + nflowSwitches.encode() + b"', shell=True)\n")

            # Configure sFlow
            sflowValues = self.appPrefs['sflow']
            if len(sflowValues['sflowTarget']) > 0:
                sflowEnabled = False
                sflowSwitches = ''
                sflowAPs = ''
                for widget in self.widgetToItem:
                    name = widget['text']
                    tags = self.canvas.gettags(self.widgetToItem[widget])

                    if 'Switch' in tags:
                        opts = self.switchOpts[name]
                        if 'sflow' in opts:
                            if opts['sflow'] == '1':
                                sflowSwitches = sflowSwitches + ' -- set Bridge ' + name + ' sflow=@MiniEditSF'
                                sflowEnabled = True
                    elif 'AP' in tags:
                        opts = self.apOpts[name]
                        if 'sflow' in opts:
                            if opts['sflow'] == '1':
                                sflowAPs = sflowAPs + ' -- set Bridge ' + name + ' sflow=@MiniEditSF'
                                sflowEnabled = True
                if sflowEnabled:
                    sflowCmd = 'ovs-vsctl -- --id=@MiniEditSF create sFlow ' + 'target=\\\"' + sflowValues[
                        'sflowTarget'] + '\\\" ' + 'header=' + sflowValues['sflowHeader'] + ' ' + 'sampling=' + \
                               sflowValues['sflowSampling'] + ' ' + 'polling=' + sflowValues['sflowPolling']
                    f.write(b"    \n")
                    f.write(b"    call('" + sflowCmd.encode() + sflowSwitches.encode() + b"', shell=True)\n")

            f.write(b"\n")
            f.write(b"    CLI(net)\n")
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Host' in tags or 'Station' in tags:
                    if 'Host' in tags:
                        opts = self.hostOpts[name]
                    else:
                        opts = self.stationOpts[name]
                    # Run User Defined Stop Command
                    if 'stopCommand' in opts:
                        f.write(b"    " + name.encode() + b".cmdPrint('" + opts['stopCommand'].encode() + b"')\n")
                if 'Switch' in tags or 'AP' in tags:
                    if 'Switch' in tags:
                        opts = self.switchOpts[name]
                    else:
                        opts = self.apOpts[name]
                    # Run User Defined Stop Command
                    if 'stopCommand' in opts:
                        f.write(b"    " + name.encode() + b".cmdPrint('" + opts['stopCommand'].encode() + b"')\n")

            f.write(b"    net.stop()\n")
            f.write(b"\n")
            f.write(b"\n")
            f.write(b"if __name__ == '__main__':\n")
            f.write(b"    setLogLevel( 'info' )\n")
            f.write(b"    myNetwork()\n")
            f.write(b"\n")
            f.close()

    # Generic canvas handler
    #
    # We could have used bindtags, as in nodeIcon, but
    # the dynamic approach used here
    # may actually require less code. In any case, it's an
    # interesting introspection-based alternative to bindtags.

    def canvasHandle(self, eventName, event):
        """Generic canvas event handler"""
        if self.active is None:
            return
        toolName = self.active
        handler = getattr(self, eventName + toolName, None)
        if handler is not None:
            handler(event)

    def clickCanvas(self, event):
        """Canvas click handler."""
        self.canvasHandle('click', event)

    def dragCanvas(self, event):
        """Canvas drag handler."""
        self.canvasHandle('drag', event)

    def releaseCanvas(self, event):
        """Canvas mouse up handler."""
        self.canvasHandle('release', event)

    # Currently the only items we can select directly are
    # links. Nodes are handled by bindings in the node icon.

    def findItem(self, x, y):
        """Find items at a location in our canvas."""
        items = self.canvas.find_overlapping(x, y, x, y)
        if len(items) == 0:
            return None
        return items[0]

    # Canvas bindings for Select, Host, Switch and Link tools

    def clickSelect(self, event):
        """Select an item."""
        self.selectItem(self.findItem(event.x, event.y))

    def deleteItem(self, item):
        """Delete an item."""
        # Don't delete while network is running
        if self.buttons['Select']['state'] == 'disabled':
            return
        # Delete from model
        if item in self.links:
            self.deleteLink(item)
        if item in self.itemToWidget:
            self.deleteNode(item)
        # Delete from view
        self.canvas.delete(item)

    def deleteSelection(self, _event):
        """Delete the selected item."""
        if self.selection is not None:
            self.deleteItem(self.selection)
        self.selectItem(None)

    def nodeIcon(self, node, name):
        """Create a new node icon."""
        icon = Button(self.canvas, image=self.images[node],
                      text=name, compound='top')
        # Unfortunately bindtags wants a tuple
        bindtags = [str(self.nodeBindings)]
        bindtags += list(icon.bindtags())
        icon.bindtags(tuple(bindtags))
        return icon

    def newNode(self, node, event):
        """Add a new node to our canvas."""
        c = self.canvas
        x, y = c.canvasx(event.x), c.canvasy(event.y)
        name = self.nodePrefixes[node]
        if 'Switch' == node:
            self.switchCount += 1
            name = self.nodePrefixes[node] + str(self.switchCount)
            self.switchOpts[name] = {}
            self.switchOpts[name]['nodeNum'] = self.switchCount
            self.switchOpts[name]['hostname'] = name
            self.switchOpts[name]['switchType'] = 'default'
            self.switchOpts[name]['controllers'] = []
        if 'WLC' == node:
            self.wlcCount += 1
            name = self.nodePrefixes[node] + str(self.wlcCount)
            self.wlcOpts[name] = {}
            self.wlcOpts[name]['nodeNum'] = self.wlcCount
            self.wlcOpts[name]['hostname'] = name
            self.wlcOpts[name]['wlcType'] = 'hwlc'
            self.wlcOpts[name]['controllers'] = []
        if 'AP' == node:
            self.apCount += 1
            name = self.nodePrefixes[node] + str(self.apCount)
            self.apOpts[name] = {}
            self.apOpts[name]['nodeNum'] = self.apCount
            self.apOpts[name]['hostname'] = name
            self.apOpts[name]['apType'] = 'default'
            self.apOpts[name]['ssid'] = name + '-ssid'
            self.apOpts[name]['channel'] = '1'
            self.apOpts[name]['mode'] = 'g'
            self.apOpts[name]['range'] = 'default'
            self.apOpts[name]['authentication'] = 'none'
            self.apOpts[name]['passwd'] = ''
            self.apOpts[name]['controllers'] = []
            self.apOpts[name]['wlans'] = 1
        if 'LegacyRouter' == node:
            self.switchCount += 1
            name = self.nodePrefixes[node] + str(self.switchCount)
            self.switchOpts[name] = {}
            self.switchOpts[name]['nodeNum'] = self.switchCount
            self.switchOpts[name]['hostname'] = name
            self.switchOpts[name]['switchType'] = 'legacyRouter'
        if 'LegacySwitch' == node:
            self.switchCount += 1
            name = self.nodePrefixes[node] + str(self.switchCount)
            self.switchOpts[name] = {}
            self.switchOpts[name]['nodeNum'] = self.switchCount
            self.switchOpts[name]['hostname'] = name
            self.switchOpts[name]['switchType'] = 'legacySwitch'
            self.switchOpts[name]['controllers'] = []
        if 'Host' == node:
            self.hostCount += 1
            name = self.nodePrefixes[node] + str(self.hostCount)
            self.hostOpts[name] = {'sched': 'host'}
            self.hostOpts[name]['nodeNum'] = self.hostCount
            self.hostOpts[name]['hostname'] = name
        if 'Station' == node:
            self.stationCount += 1
            name = self.nodePrefixes[node] + str(self.stationCount)
            self.stationOpts[name] = {'sched': 'station'}
            self.stationOpts[name]['nodeNum'] = self.stationCount
            self.stationOpts[name]['hostname'] = name
            self.stationOpts[name]['ssid'] = name + '-ssid'
            self.stationOpts[name]['channel'] = '1'
            self.stationOpts[name]['mode'] = 'g'
            self.stationOpts[name]['range'] = 'default'
            self.stationOpts[name]['passwd'] = ''
            self.stationOpts[name]['user'] = ''
            self.stationOpts[name]['wpans'] = 0
            self.stationOpts[name]['wlans'] = 1
        if 'Controller' == node:
            name = self.nodePrefixes[node] + str(self.controllerCount)
            ctrlr = {'controllerType': 'ref',
                     'hostname': name,
                     'controllerProtocol': 'tcp',
                     'remoteIP': '127.0.0.1',
                     'remotePort': 6653}
            self.controllers[name] = ctrlr
            # We want to start controller count at 0
            self.controllerCount += 1
        if node == 'AP' or node == 'Station':
            c = self.canvas
            if node == 'AP':
                node_ = self.apOpts[name]
                type = 'AP'
            else:
                node_ = self.stationOpts[name]
                type = 'Station'
            range = self.getRange(node_, type)

            self.range[name] = self.createCircle(x, y, range, c)

        icon = self.nodeIcon(node, name)
        item = self.canvas.create_window(x, y, anchor='c', window=icon, tags=node)
        self.widgetToItem[icon] = item
        self.itemToWidget[item] = icon
        self.selectItem(item)
        icon.links = {}
        if 'Switch' == node:
            icon.bind('<Button-3>', self.do_switchPopup)
        if 'WLC' == node:
            icon.bind('<Button-3>', self.do_wlcPopup)
        if 'AP' == node:
            icon.bind('<Button-3>', self.do_apPopup)
        if 'LegacyRouter' == node:
            icon.bind('<Button-3>', self.do_legacyRouterPopup)
        if 'LegacySwitch' == node:
            icon.bind('<Button-3>', self.do_legacySwitchPopup)
        if 'Host' == node:
            icon.bind('<Button-3>', self.do_hostPopup)
        if 'Station' == node:
            icon.bind('<Button-3>', self.do_stationPopup)
        if 'Controller' == node:
            icon.bind('<Button-3>', self.do_controllerPopup)

    def createCircle(self, x, y, range, c):
        return c.create_oval(x - range, y - range,
                             x + range, y + range,
                             outline="#0000ff", width=2)

    def clickController(self, event):
        """Add a new Controller to our canvas."""
        self.newNode('Controller', event)

    def clickHost(self, event):
        """Add a new host to our canvas."""
        self.newNode('Host', event)

    def clickStation(self, event):
        """Add a new station to our canvas."""
        self.newNode('Station', event)

    def clickLegacyRouter(self, event):
        """Add a new switch to our canvas."""
        self.newNode('LegacyRouter', event)

    def clickLegacySwitch(self, event):
        """Add a new switch to our canvas."""
        self.newNode('LegacySwitch', event)

    def clickSwitch(self, event):
        """Add a new switch to our canvas."""
        self.newNode('Switch', event)

    def clickWLC(self, event):
        """Add a new wlc to our canvas."""
        self.newNode('WLC', event)

    def clickAP(self, event):
        """Add a new ap to our canvas."""
        self.newNode('AP', event)

    def getRange(self, node, type):
        if node['range'] == 'default':
            range = 188 if node['mode'] == 'a' else 313
        else:
            range = node['range']

        return int(range)

    def dragNetLink(self, event):
        """Drag a link's endpoint to another node."""
        if self.link is None:
            return
        # Since drag starts in widget, we use root coords
        x = self.canvasx(event.x_root)
        y = self.canvasy(event.y_root)
        c = self.canvas
        c.coords(self.link, self.linkx, self.linky, x, y)

    def releaseNetLink(self, _event):
        """Give up on the current link."""
        if self.link is not None:
            self.canvas.delete(self.link)
        self.linkWidget = self.linkItem = self.link = None

    # Generic node handlers

    def createNodeBindings(self):
        """Create a set of bindings for nodes."""
        bindings = {
            '<ButtonPress-1>': self.clickNode,
            '<B1-Motion>': self.dragNode,
            '<ButtonRelease-1>': self.releaseNode,
            '<Enter>': self.enterNode,
            '<Leave>': self.leaveNode
        }
        l = Label()  # lightweight-ish owner for bindings
        for event, binding in bindings.items():
            l.bind(event, binding)
        return l

    def selectItem(self, item):
        """Select an item and remember old selection."""
        self.lastSelection = self.selection
        self.selection = item

    def enterNode(self, event):
        """Select node on entry."""
        self.selectNode(event)

    def leaveNode(self, _event):
        """Restore old selection on exit."""
        self.selectItem(self.lastSelection)

    def clickNode(self, event):
        """Node click handler."""
        if self.active == 'NetLink':
            self.startLink(event)
        else:
            self.selectNode(event)
        return 'break'

    def dragNode(self, event):
        """Node drag handler."""
        if self.active == 'NetLink':
            self.dragNetLink(event)
        else:
            self.dragNodeAround(event)

    def releaseNode(self, event):
        """Node release handler."""
        if self.active == 'NetLink':
            self.finishLink(event)

    # Specific node handlers

    def selectNode(self, event):
        """Select the node that was clicked on."""
        item = self.widgetToItem.get(event.widget, None)
        self.selectItem(item)

    def setPosition(self, node, x, y):
        node.setPosition('%s,%s,0' % (x, y))

    def dragNodeAround(self, event):
        """Drag a node around on the canvas."""
        c = self.canvas
        # Convert global to local coordinates;
        # Necessary since x, y are widget-relative
        x = self.canvasx(event.x_root)
        y = self.canvasy(event.y_root)
        w = event.widget
        # Adjust node position
        item = self.widgetToItem[w]
        c.coords(item, x, y)

        tags = self.canvas.gettags(item)
        if 'Station' in tags or 'AP' in tags:
            widget = self.itemToWidget[item]
            name = widget['text']
            if 'AP' in tags:
                node = self.apOpts[name]
                type = 'AP'
            else:
                node = self.stationOpts[name]
                type = 'Station'
            range = self.getRange(node, type)
            c.coords(self.range[name],
                     x - range, y - range,
                     x + range, y + range)
        # Adjust link positions
        for dest in w.links:
            link = w.links[dest]
            item = self.widgetToItem[dest]
            x1, y1 = c.coords(item)
            c.coords(link, x, y, x1, y1)

        if self.net and ('Station' in tags or 'AP' in tags):
            self.setPosition(self.net.getNodeByName(name), x, y)
        self.updateScrollRegion()

    def createControlLinkBindings(self):
        """Create a set of bindings for nodes."""

        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event

        def select(_event, link=self.link):
            """Select item on mouse entry."""
            self.selectItem(link)

        def highlight(_event, link=self.link):
            """Highlight item on mouse entry."""
            self.selectItem(link)
            self.canvas.itemconfig(link, fill='green')

        def unhighlight(_event, link=self.link):
            """Unhighlight item on mouse exit."""
            self.canvas.itemconfig(link, fill='red')
            # self.selectItem( None )

        self.canvas.tag_bind(self.link, '<Enter>', highlight)
        self.canvas.tag_bind(self.link, '<Leave>', unhighlight)
        self.canvas.tag_bind(self.link, '<ButtonPress-1>', select)

    def createDataLinkBindings(self):
        """Create a set of bindings for nodes."""

        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event

        def select(_event, link=self.link):
            """Select item on mouse entry."""
            self.selectItem(link)

        def highlight(_event, link=self.link):
            """Highlight item on mouse entry."""
            self.selectItem(link)
            self.canvas.itemconfig(link, fill='green')

        def unhighlight(_event, link=self.link):
            """Unhighlight item on mouse exit."""
            self.canvas.itemconfig(link, fill='blue')
            # self.selectItem( None )

        self.canvas.tag_bind(self.link, '<Enter>', highlight)
        self.canvas.tag_bind(self.link, '<Leave>', unhighlight)
        self.canvas.tag_bind(self.link, '<ButtonPress-1>', select)
        self.canvas.tag_bind(self.link, '<Button-3>', self.do_linkPopup)

    def startLink(self, event):
        """Start a new link."""
        if event.widget not in self.widgetToItem:
            # Didn't click on a node
            return

        w = event.widget
        item = self.widgetToItem[w]
        x, y = self.canvas.coords(item)
        self.link = self.canvas.create_line(x, y, x, y, width=4,
                                            fill='blue', tag='link')
        self.linkx, self.linky = x, y
        self.linkWidget = w
        self.linkItem = item

    def finishLink(self, event):
        """Finish creating a link"""
        if self.link is None:
            return
        source = self.linkWidget
        c = self.canvas
        # Since we dragged from the widget, use root coords
        x, y = self.canvasx(event.x_root), self.canvasy(event.y_root)
        target = self.findItem(x, y)
        dest = self.itemToWidget.get(target, None)
        if (source is None or dest is None or source == dest
                or dest in source.links or source in dest.links):
            self.releaseNetLink(event)
            return
        # For now, don't allow hosts to be directly linked
        stags = self.canvas.gettags(self.widgetToItem[source])
        dtags = self.canvas.gettags(target)
        if (('Controller' in dtags and 'LegacyRouter' in stags) or
                ('Controller' in stags and 'LegacyRouter' in dtags) or
                ('Controller' in dtags and 'LegacySwitch' in stags) or
                ('Controller' in stags and 'LegacySwitch' in dtags) or
                ('Controller' in dtags and 'Host' in stags) or
                ('Controller' in stags and 'Host' in dtags) or
                ('Controller' in stags and 'Controller' in dtags)):
            self.releaseNetLink(event)
            return

        # Set link type
        linkType = 'data'
        if 'Controller' in stags or 'Controller' in dtags:
            linkType = 'control'
            c.itemconfig(self.link, dash=(6, 4, 2, 4), fill='red')
            self.createControlLinkBindings()
        elif 'Station' in stags and 'AP' in dtags:
            linkType = 'data'
            c.itemconfig(self.link, dash=(4, 2, 4, 2), fill='blue')
            self.createDataLinkBindings()
        elif 'AP' in stags and 'Station' in dtags:
            linkType = 'data'
            c.itemconfig(self.link, dash=(4, 2, 4, 2), fill='blue')
            self.createDataLinkBindings()
        else:
            linkType = 'data'
            self.createDataLinkBindings()
        c.itemconfig(self.link, tags=c.gettags(self.link) + (linkType,))

        x, y = c.coords(target)
        c.coords(self.link, self.linkx, self.linky, x, y)
        self.addLink(source, dest, linktype=linkType)
        if linkType == 'control':
            controllerName = ''
            switchName = ''
            if 'Controller' in stags:
                controllerName = source['text']
                switchName = dest['text']
            else:
                controllerName = dest['text']
                switchName = source['text']

            try:
                self.switchOpts[switchName]['controllers'].append(controllerName)
            except:
                self.apOpts[switchName]['controllers'].append(controllerName)

        # We're done
        self.link = self.linkWidget = None

    # Menu handlers

    def about(self):
        """Display about box."""
        about = self.aboutBox
        if about is None:
            bg = 'white'
            about = Toplevel(bg='white')
            about.title('About')
            desc = self.appName + ': a simple network editor'
            version = 'Network Editor ' + MINIEDIT_VERSION
            author = 'Enhanced by: Aleksandr Loshkarev'
            www = 'http://eltex-co.ru'
            line1 = Label(about, text=desc, font='Helvetica 10 bold', bg=bg)
            line2 = Label(about, text=version, font='Helvetica 9', bg=bg)
            line3 = Label(about, text=author, font='Helvetica 9', bg=bg)
            line4 = Entry(about, font='Helvetica 9', bg=bg, width=len(www), justify=CENTER)
            line4.insert(0, www)
            line4.configure(state='readonly')
            line1.pack(padx=20, pady=10)
            line2.pack(pady=10)
            line3.pack(pady=10)
            line4.pack(pady=10)
            hide = (lambda about=about: about.withdraw())
            self.aboutBox = about
            # Hide on close rather than destroying window
            Wm.wm_protocol(about, name='WM_DELETE_WINDOW', func=hide)
        # Show (existing) window
        about.deiconify()

    def createToolImages(self):
        """Create toolbar (and icon) images."""

    @staticmethod
    def checkIntf(intf):
        """Make sure intf exists and is not configured."""
        if (' %s:' % intf) not in quietRun('ip link show'):
            messagebox.showerror(title="Error",
                                 message='External interface ' + intf + ' does not exist! Skipping.')
            return False
        ips = re.findall(r'\d+\.\d+\.\d+\.\d+', quietRun('ifconfig ' + intf))
        if ips:
            messagebox.showerror(title="Error",
                                 message=intf + ' has an IP address and is probably in use! Skipping.')
            return False
        return True

    def hostDetails(self, _ignore=None):
        if (self.selection is None or
                self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        if 'Host' not in tags:
            return

        prefDefaults = self.hostOpts[name]
        hostBox = HostDialog(self, title='Host Details', prefDefaults=prefDefaults)
        self.master.wait_window(hostBox.top)
        if hostBox.result:
            newHostOpts = {'nodeNum': self.hostOpts[name]['nodeNum']}
            newHostOpts['sched'] = hostBox.result['sched']
            if len(hostBox.result['startCommand']) > 0:
                newHostOpts['startCommand'] = hostBox.result['startCommand']
            if len(hostBox.result['stopCommand']) > 0:
                newHostOpts['stopCommand'] = hostBox.result['stopCommand']
            if len(hostBox.result['cpu']) > 0:
                newHostOpts['cpu'] = float(hostBox.result['cpu'])
            if len(hostBox.result['cores']) > 0:
                newHostOpts['cores'] = hostBox.result['cores']
            if len(hostBox.result['hostname']) > 0:
                newHostOpts['hostname'] = hostBox.result['hostname']
                name = hostBox.result['hostname']
                widget['text'] = name
            if len(hostBox.result['defaultRoute']) > 0:
                newHostOpts['defaultRoute'] = hostBox.result['defaultRoute']
            if len(hostBox.result['ip']) > 0:
                newHostOpts['ip'] = hostBox.result['ip']
            if len(hostBox.result['externalInterfaces']) > 0:
                newHostOpts['externalInterfaces'] = hostBox.result['externalInterfaces']
            if len(hostBox.result['vlanInterfaces']) > 0:
                newHostOpts['vlanInterfaces'] = hostBox.result['vlanInterfaces']
            if len(hostBox.result['privateDirectory']) > 0:
                newHostOpts['privateDirectory'] = hostBox.result['privateDirectory']
            self.hostOpts[name] = newHostOpts
            info('New host details for ' + name + ' = ' + str(newHostOpts), '\n')

    def stationDetails(self, _ignore=None):
        if (self.selection is None or
                self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        if 'Station' not in tags:
            return

        prefDefaults = self.stationOpts[name]
        stationBox = StationDialog(self, title='Station Details', prefDefaults=prefDefaults)
        self.master.wait_window(stationBox.top)
        if stationBox.result:
            newStationOpts = {'nodeNum': self.stationOpts[name]['nodeNum']}
            newStationOpts['mode'] = stationBox.result['mode']
            newStationOpts['sched'] = stationBox.result['sched']
            newStationOpts['range'] = stationBox.result['range']
            if len(stationBox.result['startCommand']) > 0:
                newStationOpts['startCommand'] = stationBox.result['startCommand']
            if len(stationBox.result['stopCommand']) > 0:
                newStationOpts['stopCommand'] = stationBox.result['stopCommand']
            if len(stationBox.result['cpu']) > 0:
                newStationOpts['cpu'] = float(stationBox.result['cpu'])
            if len(stationBox.result['cores']) > 0:
                newStationOpts['cores'] = stationBox.result['cores']
            if len(stationBox.result['hostname']) > 0:
                newStationOpts['hostname'] = stationBox.result['hostname']
                name = stationBox.result['hostname']
                widget['text'] = name
            if len(stationBox.result['passwd']) > 0:
                newStationOpts['passwd'] = stationBox.result['passwd']
            if len(stationBox.result['user']) > 0:
                newStationOpts['user'] = stationBox.result['user']
            if len(stationBox.result['wpans']) > 0:
                newStationOpts['wpans'] = int(stationBox.result['wpans'])
            if len(stationBox.result['wlans']) > 0:
                newStationOpts['wlans'] = int(stationBox.result['wlans'])
            if len(stationBox.result['defaultRoute']) > 0:
                newStationOpts['defaultRoute'] = stationBox.result['defaultRoute']
            if len(stationBox.result['ip']) > 0:
                newStationOpts['ip'] = stationBox.result['ip']
            if len(stationBox.result['externalInterfaces']) > 0:
                newStationOpts['externalInterfaces'] = stationBox.result['externalInterfaces']
            if len(stationBox.result['vlanInterfaces']) > 0:
                newStationOpts['vlanInterfaces'] = stationBox.result['vlanInterfaces']
            if len(stationBox.result['privateDirectory']) > 0:
                newStationOpts['privateDirectory'] = stationBox.result['privateDirectory']
            name = widget['text']
            x, y = self.canvas.coords(self.selection)
            range = self.getRange(newStationOpts, 'Station')
            self.canvas.coords(self.range[name],
                               x - range, y - range,
                               x + range, y + range)
            self.stationOpts[name] = newStationOpts
            info('New station details for ' + name + ' = ' + str(newStationOpts), '\n')

    def wlcDetails(self, _ignore=None):
        if (self.selection is None or
                self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        if 'WLC' not in tags:
            return

        prefDefaults = self.wlcOpts[name]
        wlcBox = WLCDialog(self, title='WLC Details', prefDefaults=prefDefaults)
        self.master.wait_window(wlcBox.top)
        if wlcBox.result:
            newWLCOpts = {'nodeNum': self.wlcOpts[name]['nodeNum']}
            newWLCOpts['wlcType'] = wlcBox.result['wlcType']
            newWLCOpts['controllers'] = self.wlcOpts[name]['controllers']
            if len(wlcBox.result['startCommand']) > 0:
                newWLCOpts['startCommand'] = wlcBox.result['startCommand']
            if len(wlcBox.result['stopCommand']) > 0:
                newWLCOpts['stopCommand'] = wlcBox.result['stopCommand']
            if len(wlcBox.result['dpctl']) > 0:
                newWLCOpts['dpctl'] = wlcBox.result['dpctl']
            if len(wlcBox.result['dpid']) > 0:
                newWLCOpts['dpid'] = wlcBox.result['dpid']
            if len(wlcBox.result['hostname']) > 0:
                newWLCOpts['hostname'] = wlcBox.result['hostname']
                name = wlcBox.result['hostname']
                widget['text'] = name
            if len(wlcBox.result['externalInterfaces']) > 0:
                newWLCOpts['externalInterfaces'] = wlcBox.result['externalInterfaces']
            newWLCOpts['wlcIP'] = wlcBox.result['wlcIP']
            newWLCOpts['sflow'] = wlcBox.result['sflow']
            newWLCOpts['netflow'] = wlcBox.result['netflow']
            self.switchOpts[name] = newWLCOpts
            info('New WLC details for ' + name + ' = ' + str(newWLCOpts), '\n')

    def switchDetails(self, _ignore=None):
        if (self.selection is None or
                self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        if 'Switch' not in tags:
            return

        prefDefaults = self.switchOpts[name]
        switchBox = SwitchDialog(self, title='Switch Details', prefDefaults=prefDefaults)
        self.master.wait_window(switchBox.top)
        if switchBox.result:
            newSwitchOpts = {'nodeNum': self.switchOpts[name]['nodeNum']}
            newSwitchOpts['switchType'] = switchBox.result['switchType']
            newSwitchOpts['controllers'] = self.switchOpts[name]['controllers']
            if len(switchBox.result['startCommand']) > 0:
                newSwitchOpts['startCommand'] = switchBox.result['startCommand']
            if len(switchBox.result['stopCommand']) > 0:
                newSwitchOpts['stopCommand'] = switchBox.result['stopCommand']
            if len(switchBox.result['dpctl']) > 0:
                newSwitchOpts['dpctl'] = switchBox.result['dpctl']
            if len(switchBox.result['dpid']) > 0:
                newSwitchOpts['dpid'] = switchBox.result['dpid']
            if len(switchBox.result['hostname']) > 0:
                newSwitchOpts['hostname'] = switchBox.result['hostname']
                name = switchBox.result['hostname']
                widget['text'] = name
            if len(switchBox.result['externalInterfaces']) > 0:
                newSwitchOpts['externalInterfaces'] = switchBox.result['externalInterfaces']
            newSwitchOpts['switchIP'] = switchBox.result['switchIP']
            newSwitchOpts['sflow'] = switchBox.result['sflow']
            newSwitchOpts['netflow'] = switchBox.result['netflow']
            self.switchOpts[name] = newSwitchOpts
            info('New switch details for ' + name + ' = ' + str(newSwitchOpts), '\n')

    def apDetails(self, _ignore=None):
        if (self.selection is None or
                # self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        if 'AP' not in tags:
            return

        prefDefaults = self.apOpts[name]
        apBox = APDialog(self, title='Access Point Details', prefDefaults=prefDefaults)
        self.master.wait_window(apBox.top)
        if apBox.result:
            newAPOpts = {'nodeNum': self.apOpts[name]['nodeNum']}
            newAPOpts['apType'] = apBox.result['apType']
            newAPOpts['authentication'] = apBox.result['authentication']
            newAPOpts['passwd'] = apBox.result['passwd']
            newAPOpts['mode'] = apBox.result['mode']
            newAPOpts['range'] = apBox.result['range']
            newAPOpts['wlans'] = int(apBox.result['wlans'])
            newAPOpts['controllers'] = self.apOpts[name]['controllers']
            if len(apBox.result['startCommand']) > 0:
                newAPOpts['startCommand'] = apBox.result['startCommand']
            if len(apBox.result['stopCommand']) > 0:
                newAPOpts['stopCommand'] = apBox.result['stopCommand']
            if len(apBox.result['dpctl']) > 0:
                newAPOpts['dpctl'] = apBox.result['dpctl']
            if len(apBox.result['dpid']) > 0:
                newAPOpts['dpid'] = apBox.result['dpid']
            if len(apBox.result['ssid']) > 0:
                newAPOpts['ssid'] = apBox.result['ssid']
            if len(apBox.result['channel']) > 0:
                newAPOpts['channel'] = apBox.result['channel']
            if len(apBox.result['hostname']) > 0:
                newAPOpts['hostname'] = apBox.result['hostname']
                name = apBox.result['hostname']
                widget['text'] = name
            if len(apBox.result['externalInterfaces']) > 0:
                newAPOpts['externalInterfaces'] = apBox.result['externalInterfaces']
            newAPOpts['apIP'] = apBox.result['apIP']
            newAPOpts['sflow'] = apBox.result['sflow']
            newAPOpts['netflow'] = apBox.result['netflow']
            self.apOpts[name] = newAPOpts
            name = widget['text']
            x, y = self.canvas.coords(self.selection)
            range = self.getRange(newAPOpts, 'AP')
            self.canvas.coords(self.range[name],
                               x - range, y - range,
                               x + range, y + range)

            if self.net:
                node = self.net.getNodeByName(newAPOpts['hostname'])
                self.setMode(node, newAPOpts['mode'])
                self.setChannel(node, newAPOpts['channel'])

            info('New access point details for ' + name + ' = ' + str(newAPOpts), '\n')

    def setChannel(self, node, channel):
        node.wintfs[0].setAPChannel(int(channel))
        if isinstance(node.wintfs[0], master):
            node.wintfs[0].set_tc_ap()
        ConfigMobLinks()

    def setMode(self, node, mode):
        node.wintfs[0].setMode(mode)

    def linkUp(self):
        if (self.selection is None or
                self.net is None):
            return
        link = self.selection
        linkDetail = self.links[link]
        src = linkDetail['src']
        dst = linkDetail['dest']
        srcName, dstName = src['text'], dst['text']
        self.net.configLinkStatus(srcName, dstName, 'up')
        self.canvas.itemconfig(link, dash=())

    def linkDown(self):
        if (self.selection is None or
                self.net is None):
            return
        link = self.selection
        linkDetail = self.links[link]
        src = linkDetail['src']
        dst = linkDetail['dest']
        srcName, dstName = src['text'], dst['text']
        self.net.configLinkStatus(srcName, dstName, 'down')
        self.canvas.itemconfig(link, dash=(4, 4))

    def linkDetails(self, _ignore=None):
        if (self.selection is None or
                self.net is not None):
            return
        link = self.selection
        linkDetail = self.links[link]
        nodeSrc = ''
        nodeDest = ''

        for widget in self.widgetToItem:
            nodeName = widget['text']
            if nodeName == linkDetail['src']['text']:
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'AP' in tags:
                    nodeSrc = self.apOpts[nodeName]
                elif 'Station' in tags:
                    nodeSrc = self.stationOpts[nodeName]
            else:
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'AP' in tags:
                    nodeDest = self.apOpts[nodeName]
                elif 'Station' in tags:
                    nodeDest = self.stationOpts[nodeName]

        linkopts = linkDetail['linkOpts']
        linkBox = LinkDialog(self, title='Link Details',
                             linkDefaults=linkopts, links=linkDetail,
                             src=nodeSrc, dest=nodeDest)
        if linkBox.result is not None:
            linkDetail['linkOpts'] = linkBox.result
            info('New link details = ' + str(linkBox.result), '\n')

    def prefDetails(self):
        prefDefaults = self.appPrefs
        prefBox = PrefsDialog(self, title='Preferences', prefDefaults=prefDefaults)
        info('New Prefs = ' + str(prefBox.result), '\n')
        if prefBox.result:
            self.appPrefs = prefBox.result

    def controllerDetails(self):
        if (self.selection is None or
                self.net is not None or
                self.selection not in self.itemToWidget):
            return
        widget = self.itemToWidget[self.selection]
        name = widget['text']
        tags = self.canvas.gettags(self.selection)
        oldName = name
        if 'Controller' not in tags:
            return

        ctrlrBox = ControllerDialog(self, title='Controller Details', ctrlrDefaults=self.controllers[name])
        if ctrlrBox.result:
            # debug( 'Controller is ' + ctrlrBox.result[0], '\n' )
            if len(ctrlrBox.result['hostname']) > 0:
                name = ctrlrBox.result['hostname']
                widget['text'] = name
            else:
                ctrlrBox.result['hostname'] = name
            self.controllers[name] = ctrlrBox.result
            info('New controller details for ' + name + ' = ' + str(self.controllers[name]), '\n')
            # Find references to controller and change name
            if oldName != name:
                for widget in self.widgetToItem:
                    switchName = widget['text']
                    tags = self.canvas.gettags(self.widgetToItem[widget])
                    if 'Switch' in tags:
                        switch = self.switchOpts[switchName]
                        if oldName in switch['controllers']:
                            switch['controllers'].remove(oldName)
                            switch['controllers'].append(name)

    def listBridge(self, _ignore=None):
        if (self.selection is None or
                self.net is None or
                self.selection not in self.itemToWidget):
            return
        name = self.itemToWidget[self.selection]['text']
        tags = self.canvas.gettags(self.selection)

        if name not in self.net.nameToNode:
            return
        if 'Switch' in tags or 'LegacySwitch' in tags:
            call([
                "xterm -T 'Bridge Details' -sb -sl 2000 -e 'ovs-vsctl list bridge " + name + "; read -p \"Press Enter to close\"' &"],
                shell=True)

    @staticmethod
    def ovsShow(_ignore=None):
        call(["xterm -T 'OVS Summary' -sb -sl 2000 -e 'ovs-vsctl show; read -p \"Press Enter to close\"' &"],
             shell=True)

    @staticmethod
    def rootTerminal(_ignore=None):
        call(["xterm -T 'Root Terminal' -sb -sl 2000 &"], shell=True)

    def addLink(self, source, dest, linktype='data', linkopts=None):
        """Add link to model."""
        if linkopts is None:
            linkopts = {}
        source.links[dest] = self.link
        dest.links[source] = self.link
        self.links[self.link] = {'type': linktype,
                                 'src': source,
                                 'dest': dest,
                                 'linkOpts': linkopts}

    def deleteLink(self, link):
        """Delete link from model."""
        pair = self.links.get(link, None)
        if pair is not None:
            source = pair['src']
            dest = pair['dest']
            del source.links[dest]
            del dest.links[source]
            stags = self.canvas.gettags(self.widgetToItem[source])
            # dtags = self.canvas.gettags( self.widgetToItem[ dest ] )
            ltags = self.canvas.gettags(link)

            if 'control' in ltags:
                controllerName = ''
                switchName = ''
                if 'Controller' in stags:
                    controllerName = source['text']
                    switchName = dest['text']
                else:
                    controllerName = dest['text']
                    switchName = source['text']

                if controllerName in self.switchOpts[switchName]['controllers']:
                    self.switchOpts[switchName]['controllers'].remove(controllerName)

        if link is not None:
            del self.links[link]

    def deleteNode(self, item):
        """Delete node (and its links) from model."""

        widget = self.itemToWidget[item]
        tags = self.canvas.gettags(item)

        if 'Controller' in tags:
            # remove from switch controller lists
            for serachwidget in self.widgetToItem:
                name = serachwidget['text']
                tags = self.canvas.gettags(self.widgetToItem[serachwidget])
                if 'Switch' in tags:
                    if widget['text'] in self.switchOpts[name]['controllers']:
                        self.switchOpts[name]['controllers'].remove(widget['text'])
                tags = []

        if 'AP' in tags:
            self.deleteItem(self.range[widget['text']])

        for link in widget.links.values():
            # Delete from view and model
            self.deleteItem(link)
        del self.itemToWidget[item]
        del self.widgetToItem[widget]

    def buildNodes(self, net):
        # Make nodes
        info("Getting Nodes.\n")
        for widget in self.widgetToItem:
            name = widget['text']
            tags = self.canvas.gettags(self.widgetToItem[widget])
            # debug( name+' has '+str(tags), '\n' )

            if 'Switch' in tags:
                opts = self.switchOpts[name]
                # debug( str(opts), '\n' )

                # Create the correct switch class
                switchParms = {}
                if 'dpctl' in opts:
                    switchParms['listenPort'] = int(opts['dpctl'])
                if 'dpid' in opts:
                    switchParms['dpid'] = opts['dpid']
                if opts['switchType'] == 'default':
                    if self.appPrefs['switchType'] == 'user':
                        switchClass = CustomUserSwitch
                    elif self.appPrefs['switchType'] == 'userns':
                        switchParms['inNamespace'] = True
                        switchClass = CustomUserSwitch
                    else:
                        switchClass = customOvs
                elif opts['switchType'] == 'user':
                    switchClass = CustomUserSwitch
                elif opts['switchType'] == 'userns':
                    switchClass = CustomUserSwitch
                    switchParms['inNamespace'] = True
                else:
                    switchClass = customOvs

                if switchClass == customOvs:
                    # Set OpenFlow versions
                    self.openFlowVersions = []
                    if self.appPrefs['openFlowVersions']['ovsOf10'] == '1':
                        self.openFlowVersions.append('OpenFlow10')
                    if self.appPrefs['openFlowVersions']['ovsOf11'] == '1':
                        self.openFlowVersions.append('OpenFlow11')
                    if self.appPrefs['openFlowVersions']['ovsOf12'] == '1':
                        self.openFlowVersions.append('OpenFlow12')
                    if self.appPrefs['openFlowVersions']['ovsOf13'] == '1':
                        self.openFlowVersions.append('OpenFlow13')
                    protoList = ",".join(self.openFlowVersions)
                    switchParms['protocols'] = protoList
                newSwitch = net.addSwitch(name, cls=switchClass, **switchParms)

                # Some post startup config
                if switchClass == CustomUserSwitch:
                    if 'switchIP' in opts:
                        if len(opts['switchIP']) > 0:
                            newSwitch.setSwitchIP(opts['switchIP'])
                if switchClass == customOvs:
                    if 'switchIP' in opts:
                        if len(opts['switchIP']) > 0:
                            newSwitch.setSwitchIP(opts['switchIP'])

                # Attach external interfaces
                if 'externalInterfaces' in opts:
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                            Intf(extInterface, node=newSwitch)

            if 'WLC' in tags:
                opts = self.wlcOpts[name]
                # debug( str(opts), '\n' )

                # Create the correct switch class
                wlcParms = {}
                if 'dpctl' in opts:
                    wlcParms['listenPort'] = int(opts['dpctl'])
                if 'dpid' in opts:
                    wlcParms['dpid'] = opts['dpid']
                if opts['wlcType'] == 'hwlc':
                    if self.appPrefs['wlcType'] == 'hwlc':
                        wlcClass = HostWLC
                    else:
                        wlcClass = ExternalWLC
                else:
                    wlcClass = ExternalWLC

                newWLC = net.addWLC(name, cls=wlcClass, **wlcParms)

                # Some post startup config
                if wlcClass == HostWLC:
                    if 'wlcIP' in opts:
                        if len(opts['wlcIP']) > 0:
                            newWLC.setWLCIP(opts['wlcIP'])
                if wlcClass == ExternalWLC:
                    if 'wlcIP' in opts:
                        if len(opts['wlcIP']) > 0:
                            newWLC.setWLCIP(opts['wlcIP'])

                # Attach external interfaces
                if 'externalInterfaces' in opts:
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                            Intf(extInterface, node=newWLC)

            elif 'AP' in tags:
                opts = self.apOpts[name]
                # debug( str(opts), '\n' )

                # Create the correct switch class
                apParms = {}
                if 'dpctl' in opts:
                    apParms['listenPort'] = int(opts['dpctl'])
                if 'dpid' in opts:
                    apParms['dpid'] = opts['dpid']
                if 'ssid' in opts:
                    apParms['ssid'] = opts['ssid']
                if 'channel' in opts:
                    apParms['channel'] = opts['channel']
                if 'range' in opts:
                    node_ = self.apOpts[name]
                    range = self.getRange(node_, 'AP')
                    apParms['range'] = range
                if 'mode' in opts:
                    apParms['mode'] = opts['mode']
                if 'wlans' in opts:
                    apParms['wlans'] = opts['wlans']
                if 'authentication' in opts:
                    apParms['authentication'] = opts['authentication']
                if 'passwd' in opts:
                    apParms['passwd'] = opts['passwd']
                if opts['apType'] == 'default':
                    if self.appPrefs['apType'] == 'user':
                        apClass = CustomUserAP
                    elif self.appPrefs['apType'] == 'userns':
                        apParms['inNamespace'] = True
                        apClass = CustomUserAP
                    else:
                        apClass = customOvsAP
                elif opts['apType'] == 'user':
                    apClass = CustomUserAP
                elif opts['apType'] == 'userns':
                    apClass = CustomUserAP
                    apParms['inNamespace'] = True
                else:
                    apClass = customOvsAP

                if apClass == customOvsAP:
                    # Set OpenFlow versions
                    self.openFlowVersions = []
                    if self.appPrefs['openFlowVersions']['ovsOf10'] == '1':
                        self.openFlowVersions.append('OpenFlow10')
                    if self.appPrefs['openFlowVersions']['ovsOf11'] == '1':
                        self.openFlowVersions.append('OpenFlow11')
                    if self.appPrefs['openFlowVersions']['ovsOf12'] == '1':
                        self.openFlowVersions.append('OpenFlow12')
                    if self.appPrefs['openFlowVersions']['ovsOf13'] == '1':
                        self.openFlowVersions.append('OpenFlow13')
                    protoList = ",".join(self.openFlowVersions)
                    apParms['protocols'] = protoList

                x1, y1 = self.canvas.coords(self.widgetToItem[widget])
                pos = x1, y1, 0

                newAP = net.addAP(name, cls=apClass,
                                           position=pos, **apParms)

                # Some post startup config
                if apClass == CustomUserAP:
                    if 'switchIP' in opts:
                        if len(opts['apIP']) > 0:
                            newAP.setAPIP(opts['switchIP'])
                if apClass == customOvsAP:
                    if 'apIP' in opts:
                        if len(opts['apIP']) > 0:
                            newAP.setAPIP(opts['apIP'])

                # Attach external interfaces
                if 'externalInterfaces' in opts:
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                            Intf(extInterface, node=newAP)
            elif 'LegacySwitch' in tags:
                newSwitch = net.addSwitch(name, cls=LegacySwitch)
            elif 'LegacyRouter' in tags:
                newSwitch = net.addHost(name, cls=LegacyRouter)
            elif 'Host' in tags:
                opts = self.hostOpts[name]
                # debug( str(opts), '\n' )
                ip = None
                defaultRoute = None
                if 'defaultRoute' in opts and len(opts['defaultRoute']) > 0:
                    defaultRoute = 'via ' + opts['defaultRoute']
                if 'ip' in opts and len(opts['ip']) > 0:
                    ip = opts['ip']
                else:
                    nodeNum = self.hostOpts[name]['nodeNum']
                    ipBaseNum, prefixLen = netParse(self.appPrefs['ipBase'])
                    ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)

                # Create the correct host class
                if 'cores' in opts or 'cpu' in opts:
                    if 'privateDirectory' in opts:
                        hostCls = partial(CPULimitedHost,
                                          privateDirs=opts['privateDirectory'])
                    else:
                        hostCls = CPULimitedHost
                else:
                    if 'privateDirectory' in opts:
                        hostCls = partial(Host,
                                          privateDirs=opts['privateDirectory'])
                    else:
                        hostCls = Host
                debug(hostCls, '\n')
                newHost = net.addHost(name, cls=hostCls, ip=ip,
                                      defaultRoute=defaultRoute)

                # Set the CPULimitedHost specific options
                if 'cores' in opts:
                    newHost.setCPUs(cores=opts['cores'])
                if 'cpu' in opts:
                    newHost.setCPUFrac(f=opts['cpu'], sched=opts['sched'])

                # Attach external interfaces
                if 'externalInterfaces' in opts:
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                            Intf(extInterface, node=newHost)
                if 'vlanInterfaces' in opts:
                    if len(opts['vlanInterfaces']) > 0:
                        info('Checking that OS is VLAN prepared\n')
                        self.pathCheck('vconfig', moduleName='vlan package')
                        moduleDeps(add='8021q')
            elif 'Station' in tags:
                opts = self.stationOpts[name]
                # debug( str(opts), '\n' )
                ip = None
                defaultRoute = None
                if 'defaultRoute' in opts and len(opts['defaultRoute']) > 0:
                    defaultRoute = 'via ' + opts['defaultRoute']
                if 'ip' in opts and len(opts['ip']) > 0:
                    ip = opts['ip']
                else:
                    nodeNum = self.stationOpts[name]['nodeNum']
                    ipBaseNum, prefixLen = netParse(self.appPrefs['ipBase'])
                    ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)

                x1, y1 = self.canvas.coords(self.widgetToItem[widget])
                pos = x1, y1, 0

                # Create the correct host class
                if 'cores' in opts or 'cpu' in opts:
                    if 'privateDirectory' in opts:
                        staCls = partial(CPULimitedStation,
                                         privateDirs=opts['privateDirectory'])
                    else:
                        staCls = CPULimitedStation
                else:
                    if 'privateDirectory' in opts:
                        staCls = partial(Station,
                                         privateDirs=opts['privateDirectory'])
                    else:
                        staCls = Station
                debug(staCls, '\n')
                newStation = net.addSta(name, cls=staCls, position=pos,
                                            ip=ip, defaultRoute=defaultRoute)
                # Set the CPULimitedHost specific options
                if 'cores' in opts:
                    newStation.setCPUs(cores=opts['cores'])
                if 'cpu' in opts:
                    newStation.setCPUFrac(f=opts['cpu'], sched=opts['sched'])

                # Attach external interfaces
                if 'externalInterfaces' in opts:
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                            Intf(extInterface, node=newStation)
                if 'vlanInterfaces' in opts:
                    if len(opts['vlanInterfaces']) > 0:
                        info('Checking that OS is VLAN prepared\n')
                        self.pathCheck('vconfig', moduleName='vlan package')
                        moduleDeps(add='8021q')
            elif 'Controller' in tags:
                opts = self.controllers[name]

                # Get controller info from panel
                controllerType = opts['controllerType']
                if 'controllerProtocol' in opts:
                    controllerProtocol = opts['controllerProtocol']
                else:
                    controllerProtocol = 'tcp'
                    opts['controllerProtocol'] = 'tcp'
                controllerIP = opts['remoteIP']
                controllerPort = opts['remotePort']

                # Make controller
                info('Getting controller selection:' + controllerType, '\n')
                if controllerType == 'remote':
                    net.addController(name=name,
                                      controller=RemoteController,
                                      ip=controllerIP,
                                      protocol=controllerProtocol,
                                      port=controllerPort)
                elif controllerType == 'inband':
                    net.addController(name=name,
                                      controller=InbandController,
                                      ip=controllerIP,
                                      protocol=controllerProtocol,
                                      port=controllerPort)
                elif controllerType == 'ovsc':
                    net.addController(name=name,
                                      controller=OVSController,
                                      protocol=controllerProtocol,
                                      port=controllerPort)
                else:
                    net.addController(name=name,
                                      controller=Controller,
                                      protocol=controllerProtocol,
                                      port=controllerPort)

            else:
                raise Exception("Cannot create mystery node: " + name)

    @staticmethod
    def pathCheck(*args, **kwargs):
        """Make sure each program in *args can be found in $PATH."""
        moduleName = kwargs.get('moduleName', 'it')
        for arg in args:
            if not quietRun('which ' + arg):
                messagebox.showerror(title="Error",
                                     message='Cannot find required executable %s.\n' % arg +
                                             'Please make sure that %s is installed ' % moduleName +
                                             'and available in your $PATH.')

    def buildLinks(self, net):
        # Make links
        info("Getting Links.\n")
        for key, link in self.links.items():
            tags = self.canvas.gettags(key)
            if 'data' in tags:
                src = link['src']
                dst = link['dest']
                linkopts = link['linkOpts']
                srcName, dstName = src['text'], dst['text']
                srcNode, dstNode = net.nameToNode[srcName], net.nameToNode[dstName]
                if linkopts:
                    net.addLink(srcNode, dstNode, cls=TCLink, **linkopts)
                else:
                    # debug( str(srcNode) )
                    # debug( str(dstNode), '\n' )
                    net.addLink(srcNode, dstNode)
                self.canvas.itemconfig(key, dash=())

    def build(self):
        """Build network based on our topology."""
        dpctl = None

        if len(self.appPrefs['dpctl']) > 0:
            dpctl = int(self.appPrefs['dpctl'])
        link = TCLink

        wmediumd_mode = None
        if self.appPrefs['enableWmediumd'] == '1':
            link = wmediumd
            wmediumd_mode = interference

        net = Wmnet(topo=None,
                    listenPort=dpctl,
                    build=False,
                    link=link,
                    wmediumd_mode=wmediumd_mode,
                    ipBase=self.appPrefs['ipBase'])

        self.buildNodes(net)
        self.buildLinks(net)

        # Build network (we have to do this separately at the moment )
        net.build()

        return net

    def postStartSetup(self):
        # Setup host details
        for widget in self.widgetToItem:
            name = widget['text']
            tags = self.canvas.gettags(self.widgetToItem[widget])
            if 'Host' in tags:
                newHost = self.net.get(name)
                opts = self.hostOpts[name]
                # Attach vlan interfaces
                if 'vlanInterfaces' in opts:
                    for vlanInterface in opts['vlanInterfaces']:
                        info('adding vlan interface ' + vlanInterface[1], '\n')
                        newHost.cmdPrint('ifconfig ' + name + '-eth0.' + vlanInterface[1] + ' ' + vlanInterface[0])
                # Run User Defined Start Command
                if 'startCommand' in opts:
                    newHost.cmdPrint(opts['startCommand'])
            elif 'Station' in tags:
                newStation = self.net.get(name)
                opts = self.stationOpts[name]
                # Attach vlan interfaces
                if 'vlanInterfaces' in opts:
                    for vlanInterface in opts['vlanInterfaces']:
                        info('adding vlan interface ' + vlanInterface[1], '\n')
                        newStation.cmdPrint('ifconfig ' + name + '-wlan0.' + vlanInterface[1] + ' ' + vlanInterface[0])
                # Run User Defined Start Command
                if 'startCommand' in opts:
                    newStation.cmdPrint(opts['startCommand'])
            if 'Switch' in tags:
                newNode = self.net.get(name)
                opts = self.switchOpts[name]
                # Run User Defined Start Command
                if 'startCommand' in opts:
                    newNode.cmdPrint(opts['startCommand'])
            if 'WLC' in tags:
                newNode = self.net.get(name)
                opts = self.wlcOpts[name]
                # Run User Defined Start Command
                if 'startCommand' in opts:
                    newNode.cmdPrint(opts['startCommand'])
            elif 'AP' in tags:
                newNode = self.net.get(name)
                opts = self.apOpts[name]
                # Run User Defined Start Command
                if 'startCommand' in opts:
                    newNode.cmdPrint(opts['startCommand'])

        # Configure NetFlow
        nflowValues = self.appPrefs['netflow']
        if len(nflowValues['nflowTarget']) > 0:
            nflowEnabled = False
            nflowSwitches = ''
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])

                if 'Switch' in tags or 'AP' in tags:
                    opts = self.switchOpts[name]
                    if 'AP' in tags:
                        opts = self.apOpts[name]
                    if 'netflow' in opts:
                        if opts['netflow'] == '1':
                            info(name + ' has Netflow enabled\n')
                            nflowSwitches = nflowSwitches + ' -- set Bridge ' + name + ' netflow=@MiniEditNF'
                            nflowEnabled = True
            if nflowEnabled:
                nflowCmd = 'ovs-vsctl -- --id=@MiniEditNF create NetFlow ' + 'target=\\\"' + nflowValues[
                    'nflowTarget'] + '\\\" ' + 'active-timeout=' + nflowValues['nflowTimeout']
                if nflowValues['nflowAddId'] == '1':
                    nflowCmd = nflowCmd + ' add_id_to_interface=true'
                else:
                    nflowCmd = nflowCmd + ' add_id_to_interface=false'
                info('cmd = ' + nflowCmd + nflowSwitches, '\n')
                call(nflowCmd + nflowSwitches, shell=True)

            else:
                info('No switches with Netflow\n')
        else:
            info('No NetFlow targets specified.\n')

        # Configure sFlow
        sflowValues = self.appPrefs['sflow']
        if len(sflowValues['sflowTarget']) > 0:
            sflowEnabled = False
            sflowSwitches = ''
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])

                if 'Switch' in tags or 'AP' in tags:
                    opts = self.switchOpts[name]
                    if 'AP' in tags:
                        opts = self.apOpts[name]
                    if 'sflow' in opts:
                        if opts['sflow'] == '1':
                            info(name + ' has sflow enabled\n')
                            sflowSwitches = sflowSwitches + ' -- set Bridge ' + name + ' sflow=@MiniEditSF'
                            sflowEnabled = True
            if sflowEnabled:
                sflowCmd = 'ovs-vsctl -- --id=@MiniEditSF create sFlow ' + 'target=\\\"' + sflowValues[
                    'sflowTarget'] + '\\\" ' + 'header=' + sflowValues['sflowHeader'] + ' ' + 'sampling=' + sflowValues[
                               'sflowSampling'] + ' ' + 'polling=' + sflowValues['sflowPolling']
                info('cmd = ' + sflowCmd + sflowSwitches, '\n')
                call(sflowCmd + sflowSwitches, shell=True)

            else:
                info('No switches with sflow\n')
        else:
            info('No sFlow targets specified.\n')

        ## NOTE: MAKE SURE THIS IS LAST THING CALLED
        # Start the CLI if enabled
        if self.appPrefs['startCLI'] == '1':
            info(
                "\n\n NOTE: PLEASE REMEMBER TO EXIT THE CLI BEFORE YOU PRESS THE STOP BUTTON. Not exiting will prevent MiniEdit from quitting and will prevent you from starting the network again during this session.\n\n")
            CLI(self.net)

    def start(self):
        """Start network."""
        if self.net is None:
            self.net = self.build()

            # Since I am going to inject per switch controllers.
            # I can't call net.start().  I have to replicate what it
            # does and add the controller options.
            # self.net.start()
            info('---* Starting %s controllers\n' % len(self.net.controllers))
            for controller in self.net.controllers:
                info(str(controller) + ' ')
                controller.start()
            info('\n')
            info('---* Starting %s switches\n' % len(self.net.switches))
            for switch in self.net.switches:
                info(switch.name + ' ')
                switch.start(self.net.controllers)
            info('\n')
            info('---* Starting %s wlcs\n' % len(self.net.wlcs))
            for wlc in self.net.wlcs:
                info(wlc.name + ' ')
                wlc.start(self.net.controllers)
            info('\n')
            info('---* Starting %s aps\n' % len(self.net.aps))
            for ap in self.net.aps:
                info(ap.name + ' ')
                ap.start(self.net.controllers)
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Switch' in tags:
                    opts = self.switchOpts[name]
                    switchControllers = []
                    for ctrl in opts['controllers']:
                        switchControllers.append(self.net.get(ctrl))
                    info(name + ' ')
                    # Figure out what controllers will manage this switch
                    self.net.get(name).start(switchControllers)
                if 'LegacySwitch' in tags:
                    self.net.get(name).start([])
                    info(name + ' ')
            info('\n')

            self.postStartSetup()

    def stop(self):
        """Stop network."""
        if self.net is not None:
            # Stop host details
            for widget in self.widgetToItem:
                name = widget['text']
                tags = self.canvas.gettags(self.widgetToItem[widget])
                if 'Host' in tags:
                    newHost = self.net.get(name)
                    opts = self.hostOpts[name]
                    # Run User Defined Stop Command
                    if 'stopCommand' in opts:
                        newHost.cmdPrint(opts['stopCommand'])
                if 'Station' in tags:
                    newStation = self.net.get(name)
                    opts = self.stationOpts[name]
                    # Run User Defined Stop Command
                    if 'stopCommand' in opts:
                        newStation.cmdPrint(opts['stopCommand'])
                if 'Switch' in tags:
                    newNode = self.net.get(name)
                    opts = self.switchOpts[name]
                    # Run User Defined Stop Command
                    if 'stopCommand' in opts:
                        newNode.cmdPrint(opts['stopCommand'])

            self.net.stop()

        cleanUpScreens()

        WifiEmu.wemu_ids = []
        Mobility.aps = []
        Mobility.stations = []
        Mobility.mobileNodes = []

        self.net = None

    def do_linkPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.linkPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.linkPopup.grab_release()
        else:
            try:
                self.linkRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.linkRunPopup.grab_release()

    def do_controllerPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.controllerPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.controllerPopup.grab_release()

    def do_legacyRouterPopup(self, event):
        # display the popup menu
        if self.net is not None:
            try:
                self.legacyRouterRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.legacyRouterRunPopup.grab_release()

    def do_hostPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.hostPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.hostPopup.grab_release()
        else:
            try:
                self.hostRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.hostRunPopup.grab_release()

    def do_stationPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.stationPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.stationPopup.grab_release()
        else:
            try:
                self.stationRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.stationRunPopup.grab_release()

    def do_legacySwitchPopup(self, event):
        # display the popup menu
        if self.net is not None:
            try:
                self.switchRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchRunPopup.grab_release()

    def do_switchPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.switchPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchPopup.grab_release()
        else:
            try:
                self.switchRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchRunPopup.grab_release()

    def do_wlcPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.wlcPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.wlcPopup.grab_release()
        else:
            try:
                self.wlcRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.wlcRunPopup.grab_release()

    def do_apPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.apPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.apPopup.grab_release()
        else:
            try:
                self.apRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.apRunPopup.grab_release()

    def xterm(self, _ignore=None):
        """Make an xterm when a button is pressed."""
        if (self.selection is None or
                self.net is None or
                self.selection not in self.itemToWidget):
            return
        name = self.itemToWidget[self.selection]['text']
        if name not in self.net.nameToNode:
            return
        term = makeTerm(self.net.nameToNode[name], 'Host', term=self.appPrefs['terminalType'])
        self.net.terms += term

    def iperf(self, _ignore=None):
        """Make an xterm when a button is pressed."""
        if (self.selection is None or
                self.net is None or
                self.selection not in self.itemToWidget):
            return
        name = self.itemToWidget[self.selection]['text']
        if name not in self.net.nameToNode:
            return
        self.net.nameToNode[name].cmd('iperf3 -s -p 5001 &')

    ### BELOW HERE IS THE TOPOLOGY IMPORT CODE ###

    def parseArgs(self):
        """Parse command-line args and return options object.
           returns: opts parse options dict"""

        if '--custom' in sys.argv:
            index = sys.argv.index('--custom')
            if len(sys.argv) > index + 1:
                filename = sys.argv[index + 1]
                self.parseCustomFile(filename)
            else:
                raise Exception('Custom file name not found')

        desc = ("The %prog utility creates Wmnet network from the\n"
                "command line. It can create parametrized topologies,\n"
                "invoke the Wmnet CLI, and run tests.")

        usage = ('%prog [options]\n'
                 '(type %prog -h for details)')

        opts = OptionParser(description=desc, usage=usage)

        addDictOption(opts, TOPOS, TOPODEF, 'topo')
        addDictOption(opts, LINKS, LINKDEF, 'link')

        opts.add_option('--custom', type='string', default=None,
                        help='read custom topo and node params from .py' +
                             'file')

        self.options, self.args = opts.parse_args()
        # We don't accept extra arguments after the options
        if self.args:
            opts.print_help()
            sys.exit()

    def setCustom(self, name, value):
        """Set custom parameters for WmnetRunner."""
        if name in ('topos', 'switches', 'aps', 'hosts', 'stations', 'controllers', 'wlcs'):
            # Update dictionaries
            param = name.upper()
            globals()[param].update(value)
        elif name == 'validate':
            # Add custom validate function
            self.validate = value
        else:
            # Add or modify global variable or class
            globals()[name] = value

    def parseCustomFile(self, fileName):
        """Parse custom file and add params before parsing cmd-line options."""
        customs = {}
        if os.path.isfile(fileName):
            with open(fileName, 'r') as f:
                exec(f.read())  # pylint: disable=exec-used
            for name, val in customs.items():
                self.setCustom(name, val)
        else:
            raise Exception('could not find custom file: %s' % fileName)

    def importTopo(self):
        info('topo=' + self.options.topo, '\n')
        if self.options.topo == 'none':
            return
        self.newTopology()
        topo = buildTopo(TOPOS, self.options.topo)
        link = customClass(LINKS, self.options.link)
        importNet = Wmnet(topo=topo, build=False, link=link)
        importNet.build()

        c = self.canvas
        rowIncrement = 100
        currentY = 100

        # Add Controllers
        info('controllers:' + str(len(importNet.controllers)), '\n')
        for controller in importNet.controllers:
            name = controller.name
            x = self.controllerCount * 100 + 100
            self.addNode('Controller', self.controllerCount,
                         float(x), float(currentY), name=name)
            icon = self.findWidgetByName(name)
            icon.bind('<Button-3>', self.do_controllerPopup)
            ctrlr = {'controllerType': 'ref',
                     'hostname': name,
                     'controllerProtocol': controller.protocol,
                     'remoteIP': controller.ip,
                     'remotePort': controller.port}
            self.controllers[name] = ctrlr

        currentY = currentY + rowIncrement
        # Add switches
        info('switches:' + str(len(importNet.switches)), '\n')
        columnCount = 0
        for switch in importNet.switches:
            name = switch.name
            self.switchOpts[name] = {}
            self.switchOpts[name]['nodeNum'] = self.switchCount
            self.switchOpts[name]['hostname'] = name
            self.switchOpts[name]['switchType'] = 'default'
            self.switchOpts[name]['controllers'] = []

            x = columnCount * 100 + 100
            self.addNode('Switch', self.switchCount,
                         float(x), float(currentY), name=name)
            icon = self.findWidgetByName(name)
            icon.bind('<Button-3>', self.do_switchPopup)
            # Now link to controllers
            for controller in importNet.controllers:
                self.switchOpts[name]['controllers'].append(controller.name)
                dest = self.findWidgetByName(controller.name)
                dx, dy = c.coords(self.widgetToItem[dest])
                self.link = c.create_line(float(x),
                                          float(currentY),
                                          dx,
                                          dy,
                                          width=4,
                                          fill='red',
                                          dash=(6, 4, 2, 4),
                                          tag='link')
                c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                self.addLink(icon, dest, linktype='control')
                self.createControlLinkBindings()
                self.link = self.linkWidget = None
            if columnCount == 9:
                columnCount = 0
                currentY = currentY + rowIncrement
            else:
                columnCount = columnCount + 1

        currentY = currentY + rowIncrement
        # Add switches
        info('aps:' + str(len(importNet.aps)), '\n')
        columnCount = 0
        for ap in importNet.aps:
            name = ap.name
            self.apOpts[name] = {}
            self.apOpts[name]['nodeNum'] = self.apCount
            self.apOpts[name]['hostname'] = name
            self.apOpts[name]['ssid'] = name + '-ssid'
            self.apOpts[name]['channel'] = '1'
            self.apOpts[name]['mode'] = 'g'
            self.apOpts[name]['range'] = 'default'
            self.apOpts[name]['authentication'] = 'none'
            self.apOpts[name]['passwd'] = ''
            self.apOpts[name]['apType'] = 'default'
            self.apOpts[name]['wlans'] = 1
            self.apOpts[name]['controllers'] = []

            x = columnCount * 100 + 100
            self.addNode('AP', self.apCount,
                         float(x), float(currentY), name=name)
            icon = self.findWidgetByName(name)
            icon.bind('<Button-3>', self.do_apPopup)
            # Now link to controllers
            for controller in importNet.controllers:
                self.switchOpts[name]['controllers'].append(controller.name)
                dest = self.findWidgetByName(controller.name)
                dx, dy = c.coords(self.widgetToItem[dest])
                self.link = c.create_line(float(x),
                                          float(currentY),
                                          dx,
                                          dy,
                                          width=4,
                                          fill='red',
                                          dash=(6, 4, 2, 4),
                                          tag='link')
                c.itemconfig(self.link, tags=c.gettags(self.link) + ('control',))
                self.addLink(icon, dest, linktype='control')
                self.createControlLinkBindings()
                self.link = self.linkWidget = None
            if columnCount == 9:
                columnCount = 0
                currentY = currentY + rowIncrement
            else:
                columnCount = columnCount + 1

        currentY = currentY + rowIncrement
        # Add hosts
        info('hosts:' + str(len(importNet.hosts)), '\n')
        columnCount = 0
        for host in importNet.hosts:
            name = host.name
            self.hostOpts[name] = {'sched': 'host'}
            self.hostOpts[name]['nodeNum'] = self.hostCount
            self.hostOpts[name]['hostname'] = name
            self.hostOpts[name]['ip'] = host.IP()

            x = columnCount * 100 + 100
            self.addNode('Host', self.hostCount,
                         float(x), float(currentY), name=name)
            icon = self.findWidgetByName(name)
            icon.bind('<Button-3>', self.do_hostPopup)
            if columnCount == 9:
                columnCount = 0
                currentY = currentY + rowIncrement
            else:
                columnCount = columnCount + 1

        currentY = currentY + rowIncrement
        # Add hosts
        info('stations:' + str(len(importNet.stations)), '\n')
        columnCount = 0
        for station in importNet.stations:
            name = station.name
            self.stationOpts[name] = {'sched': 'station'}
            self.stationOpts[name]['nodeNum'] = self.stationCount
            self.stationOpts[name]['hostname'] = name
            self.stationOpts[name]['ip'] = station.IP()

            x = columnCount * 100 + 100
            self.addNode('Station', self.stationCount,
                         float(x), float(currentY), name=name)
            icon = self.findWidgetByName(name)
            icon.bind('<Button-3>', self.do_stationPopup)
            if columnCount == 9:
                columnCount = 0
                currentY = currentY + rowIncrement
            else:
                columnCount = columnCount + 1

        info('links:' + str(len(topo.links())), '\n')
        # [('h1', 's3'), ('h2', 's4'), ('s3', 's4')]
        for link in topo.links():
            info(str(link), '\n')
            srcNode = link[0]
            src = self.findWidgetByName(srcNode)
            sx, sy = self.canvas.coords(self.widgetToItem[src])

            destNode = link[1]
            dest = self.findWidgetByName(destNode)
            dx, dy = self.canvas.coords(self.widgetToItem[dest])

            params = topo.linkInfo(srcNode, destNode)
            info('Link Parameters=' + str(params), '\n')

            self.link = self.canvas.create_line(sx, sy, dx, dy, width=4,
                                                fill='blue', tag='link')
            c.itemconfig(self.link, tags=c.gettags(self.link) + ('data',))
            self.addLink(src, dest, linkopts=params)
            self.createDataLinkBindings()
            self.link = self.linkWidget = None

        importNet.stop()


def miniEditImages():
    """Create and return images for MiniEdit."""

    # Image data. Git will be unhappy. However, the alternative
    # is to keep track of separate binary files, which is also
    # unappealing.

    return {
        'Select': BitmapImage(
            file='/usr/include/X11/bitmaps/left_ptr'),

        'Switch': PhotoImage(file="apns/examples/veditor/images/sl2.png"),

        'AP': PhotoImage(file="apns/examples/veditor/images/ap.png"),

        'LegacySwitch': PhotoImage(file="apns/examples/veditor/images/sl2.png"),

        'LegacyRouter': PhotoImage(file="apns/examples/veditor/images/router.png"),

        'Controller': PhotoImage(file="apns/examples/veditor/images/controller.png"),

        'Host': PhotoImage(file="apns/examples/veditor/images/host.png"),

        'Station': PhotoImage(file="apns/examples/veditor/images/station.png"),

        'Phone': PhotoImage(file="apns/examples/veditor/images/phone.png"),

        'OldSwitch': PhotoImage(file="apns/examples/veditor/images/sl2.png"),

        'WLC': PhotoImage(file="apns/examples/veditor/images/wlc.png"),

        'NetLink': PhotoImage(data=r"""
            R0lGODlhFgAWAPcAMf//////zP//mf//Zv//M///AP/M///MzP/M
            mf/MZv/MM//MAP+Z//+ZzP+Zmf+ZZv+ZM/+ZAP9m//9mzP9mmf9m
            Zv9mM/9mAP8z//8zzP8zmf8zZv8zM/8zAP8A//8AzP8Amf8AZv8A
            M/8AAMz//8z/zMz/mcz/Zsz/M8z/AMzM/8zMzMzMmczMZszMM8zM
            AMyZ/8yZzMyZmcyZZsyZM8yZAMxm/8xmzMxmmcxmZsxmM8xmAMwz
            /8wzzMwzmcwzZswzM8wzAMwA/8wAzMwAmcwAZswAM8wAAJn//5n/
            zJn/mZn/Zpn/M5n/AJnM/5nMzJnMmZnMZpnMM5nMAJmZ/5mZzJmZ
            mZmZZpmZM5mZAJlm/5lmzJlmmZlmZplmM5lmAJkz/5kzzJkzmZkz
            ZpkzM5kzAJkA/5kAzJkAmZkAZpkAM5kAAGb//2b/zGb/mWb/Zmb/
            M2b/AGbM/2bMzGbMmWbMZmbMM2bMAGaZ/2aZzGaZmWaZZmaZM2aZ
            AGZm/2ZmzGZmmWZmZmZmM2ZmAGYz/2YzzGYzmWYzZmYzM2YzAGYA
            /2YAzGYAmWYAZmYAM2YAADP//zP/zDP/mTP/ZjP/MzP/ADPM/zPM
            zDPMmTPMZjPMMzPMADOZ/zOZzDOZmTOZZjOZMzOZADNm/zNmzDNm
            mTNmZjNmMzNmADMz/zMzzDMzmTMzZjMzMzMzADMA/zMAzDMAmTMA
            ZjMAMzMAAAD//wD/zAD/mQD/ZgD/MwD/AADM/wDMzADMmQDMZgDM
            MwDMAACZ/wCZzACZmQCZZgCZMwCZAABm/wBmzABmmQBmZgBmMwBm
            AAAz/wAzzAAzmQAzZgAzMwAzAAAA/wAAzAAAmQAAZgAAM+4AAN0A
            ALsAAKoAAIgAAHcAAFUAAEQAACIAABEAAADuAADdAAC7AACqAACI
            AAB3AABVAABEAAAiAAARAAAA7gAA3QAAuwAAqgAAiAAAdwAAVQAA
            RAAAIgAAEe7u7t3d3bu7u6qqqoiIiHd3d1VVVURERCIiIhEREQAA
            ACH5BAEAAAAALAAAAAAWABYAAAhIAAEIHEiwoEGBrhIeXEgwoUKG
            Cx0+hGhQoiuKBy1irChxY0GNHgeCDAlgZEiTHlFuVImRJUWXEGEy
            lBmxI8mSNknm1Dnx5sCAADs=
        """)
    }


def addDictOption(opts, choicesDict, default, name, helpStr=None):
    """Convenience function to add choices dicts to OptionParser.
       opts: OptionParser instance
       choicesDict: dictionary of valid choices, must include default
       default: default choice key
       name: long option name
       help: string"""
    if default not in choicesDict:
        raise Exception('Invalid  default %s for choices dict: %s' %
                        (default, name))
    if not helpStr:
        helpStr = ('|'.join(sorted(choicesDict.keys())) +
                   '[,param=value...]')
    opts.add_option('--' + name,
                    type='string',
                    default=default,
                    help=helpStr)


if __name__ == '__main__':
    setLogLevel('info')
    app = MiniEdit()
    ### import topology if specified ###
    app.parseArgs()
    app.importTopo()

    app.mainloop()
