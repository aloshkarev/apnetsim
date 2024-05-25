#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import os.path
import shutil

import ansible.constants as C
from ansible import context
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.inventory.manager import InventoryManager
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager

import apns


class ResultsCollectorJSONCallback(CallbackBase):

    def __init__(self, *args, **kwargs):
        super(ResultsCollectorJSONCallback, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        host = result._host
        self.host_unreachable[host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        host = result._host
        self.host_ok[host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        host = result._host
        self.host_failed[host.get_name()] = result


def install():
    host_list = 'localhost'
    context.CLIARGS = ImmutableDict(module_path=[os.path.dirname(__file__) + '/library'])
    loader = DataLoader()

    results_callback = ResultsCollectorJSONCallback()

    inventory = InventoryManager(loader=loader, sources=host_list)

    variable_manager = VariableManager(loader=loader, inventory=inventory)

    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=None,
        # stdout_callback=results_callback,
    )

    play_source = dict(
        name="AP Emulator",
        hosts='localhost',
        tasks=[
            dict(name="add local repo", action=dict(module='ansible.builtin.apt_repository', args=dict(
                repo="deb [trusted=yes] http://wifi.eltex.loc:4567/deb/ /", state='present'))),
            dict(name="apt-get update", action=dict(module='apt', args=dict(update_cache='yes'))),
            dict(name="Install dependency packages",
                 action=dict(module='apt',
                             args=dict(name=['aptitude', 'apt-transport-https', 'ca-certificates', 'curl',
                                             'python3-setuptools', 'python3-dev', 'build-essential',
                                             'iptables', 'software-properties-common', 'iproute2', 'wireless-tools',
                                             'atftpd', 'ethtool', 'wget', 'bridge-utils', 'openvswitch-switch',
                                             'rfkill', 'iw',
                                             'ansible', 'net-tools', 'libnl-3-dev', 'cmake', 'dwarves',
                                             'linux-lowlatency']))),
            dict(name="Install aprf-drv-dkms",
                 action=dict(module='apt',
                             args=dict(name=['aprf-drv-dkms', 'wmediumd-srv', 'aprf-ctrl']))),
            dict(name="install Docker CE repos (1/3)", action=dict(module='apt_key',
                                                                   args=dict(
                                                                       url='https://download.docker.com/linux/ubuntu/gpg',
                                                                       state='present'))),
            dict(name="install Docker CE repos (2/3)", action=dict(module='apt_repository',
                                                                   args=dict(
                                                                       repo="deb [arch=amd64] https://download.docker.com/linux/ubuntu {{ ansible_distribution_release }} stable",
                                                                       state='present')
                                                                   )
                 ),
            dict(name="install Docker CE repos (3/3)", action=dict(module='apt', args=dict(update_cache='yes'))),
            dict(name="install Docker CE", action=dict(module='apt', args=dict(name='docker-ce', state='present'))),
            dict(name="Check insecure registries in Docker", action=dict(
                module='json_patch',
                args=dict(
                    src='/etc/docker/daemon.json',
                    operations=[{"op": "add", "path": "/insecure-registries", "value": ["wifi.eltex.loc:5000"]}],
                    pretty='yes',
                    create='yes'))
                 ),
            dict(name="Docker service restart", action=dict(module='command', args="service docker restart")),
            dict(name="download AP emulator docker image",
                 action=dict(module='command', args="docker pull wifi.eltex.loc:5000/apemu:latest")),
            dict(name="download station docker image",
                 action=dict(module='command', args="docker pull wifi.eltex.loc:5000/sta:latest")),
            dict(name="cmake mnexec", action=dict(module='shell',
                                                  args=dict(cmd='cmake .',
                                                            chdir=os.path.dirname(apns.__file__) + '/mnexec'))),
            dict(name="make install mnexec", action=dict(module='make',
                                                         args=dict(
                                                             chdir=os.path.dirname(apns.__file__) + '/mnexec',
                                                             target='install'))),
            dict(name="ldconfig", action=dict(module='command',
                                              args='ldconfig')),
            dict(name="Make /var/run/sshd folder", action=dict(module='file',
                                                               args=dict(path="/var/run/sshd",
                                                                         state='directory',
                                                                         recurse='yes'))),
            dict(name="update python modules", action=dict(module='shell',
                                                           args='pip3.10 install -i http://wifi.eltex.loc:4567/apemu --upgrade --trusted-host wifi.eltex.loc apns')),
            dict(name="set vm.swappiness", action=dict(module='ansible.posix.sysctl',
                                                       args=dict(name="vm.swappiness",
                                                                 value='10',
                                                                 state='present'
                                                                 ))),
            dict(name="set vm.dirty_ratio", action=dict(module='ansible.posix.sysctl',
                                                        args=dict(name="vm.dirty_ratio",
                                                                  value='60',
                                                                  state='present'
                                                                  ))),
            dict(name="set vm.dirty_background_ratio", action=dict(module='ansible.posix.sysctl',
                                                                   args=dict(name="vm.dirty_background_ratio",
                                                                             value='2',
                                                                             state='present'
                                                                             ))),
            dict(name="set net.ipv4.neigh.default.gc_thresh1", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv4.neigh.default.gc_thresh1",
                                                                               value='30000',
                                                                               state='present'
                                                                               ))),
            dict(name="set net.ipv4.neigh.default.gc_thresh2", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv4.neigh.default.gc_thresh2",
                                                                               value='32000',
                                                                               state='present'
                                                                               ))),
            dict(name="set net.ipv4.neigh.default.gc_thresh3", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv4.neigh.default.gc_thresh3",
                                                                               value='32768',
                                                                               state='present'
                                                                               ))),
            dict(name="set net.ipv6.neigh.default.gc_thresh1", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv6.neigh.default.gc_thresh1",
                                                                               value='30000',
                                                                               state='present'
                                                                               ))),
            dict(name="set net.ipv6.neigh.default.gc_thresh2", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv6.neigh.default.gc_thresh2",
                                                                               value='32000',
                                                                               state='present'
                                                                               ))),
            dict(name="set net.ipv6.neigh.default.gc_thresh3", action=dict(module='ansible.posix.sysctl',
                                                                           args=dict(
                                                                               name="net.ipv6.neigh.default.gc_thresh3",
                                                                               value='32768',
                                                                               state='present'
                                                                               ))),
            dict(name="set fs.inotify.max_user_instances", action=dict(module='ansible.posix.sysctl',
                                                                       args=dict(
                                                                           name="fs.inotify.max_user_instances",
                                                                           value='8192',
                                                                           state='present'
                                                                       ))),
            dict(name="set fs.inotify.max_user_watches", action=dict(module='ansible.posix.sysctl',
                                                                       args=dict(
                                                                           name="fs.inotify.max_user_watches",
                                                                           value='524288',
                                                                           state='present'
                                                                       ))),
            dict(name="set net.core.rmem_max", action=dict(module='ansible.posix.sysctl',
                                                                     args=dict(
                                                                         name="net.core.rmem_max",
                                                                         value='16777216',
                                                                         state='present'
                                                                     ))),
            dict(name="set net.core.wmem_max", action=dict(module='ansible.posix.sysctl',
                                                                     args=dict(
                                                                         name="net.core.wmem_max",
                                                                         value='16777216',
                                                                         state='present'
                                                                     ))),
            dict(name="set net.ipv4.tcp_window_scaling", action=dict(module='ansible.posix.sysctl',
                                                                     args=dict(
                                                                         name="net.ipv4.tcp_window_scaling",
                                                                         value='1',
                                                                         state='present'
                                                                     ))),
            dict(name="set net.ipv4.tcp_sack", action=dict(module='ansible.posix.sysctl',
                                                                     args=dict(
                                                                         name="net.ipv4.tcp_sack",
                                                                         value='1',
                                                                         state='present'
                                                                     )))
        ]
    )

    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    try:
        result = tqm.run(play)
    finally:
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()

    shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)


if __name__ == '__main__':
    install()
