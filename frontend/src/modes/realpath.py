import tkinter as tk
import subprocess
import time
from threading import Thread

from tkinter import ttk
from typing import List, Optional

from modes.mode import Mode
from utils.logger import Logger
from constants import *
from utils.utils import run_fail_on_error, run_log_on_error
from models.config import *


class RealpathMode:
    def __init__(self, config: FullConfig, right_interface: str, 
                 left_interface: str, maingui, debug: bool = False):
        self.right_interface = right_interface
        self.left_interface = left_interface
        self.debug = debug
        self.maingui = maingui
        self.config = config

        self.modes: List[RealpathModeEntry] = []
        for subconfig in self.config.extended.configs:
            self.modes.append(RealpathModeEntry(config=subconfig,
                                                left_vlan_interface=config.extended.get_left_interface_name(),
                                                base_interface=right_interface,
                                                debug=debug, maingui=maingui))

    def add_tabs(self, window) -> None:
        for mode in self.modes:
            mode.add_tabs(window)

    def config_interfaces(self) -> None:
        def exec_in_default(cmd):
            run_fail_on_error(cmd, sudo=True, dryrun=self.debug)

        # Config left interface
        exec_in_default(f"ip link set up {self.left_interface}")
        exec_in_default(f"ip link add link {self.left_interface} name {self.config.extended.get_left_interface_name()} type vlan id {self.config.extended.left_vlan}")
        exec_in_default(f"ip addr add {self.config.general.left_interface_address} dev {self.config.extended.get_left_interface_name()}")
        exec_in_default(f"ip link set up dev {self.config.extended.get_left_interface_name()}")

        # Setup backrouting (right) namespace and interfaces
        exec_in_default(f"ip netns add {PUBLIC_NETNS_NAME}")
        exec_in_default(f"ip link set up {self.right_interface}")
        exec_in_default(f"ip link add link {self.right_interface} name {self.config.extended.public_interface.get_public_interface_name()} type vlan id {self.config.extended.public_interface.vlan}")
        exec_in_default(f"ip link set up dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_default(f"ip link set dev {self.config.extended.public_interface.get_public_interface_name()} netns {PUBLIC_NETNS_NAME}")

        def exec_in_netns(cmd):
            run_fail_on_error(f"ip netns exec {PUBLIC_NETNS_NAME} {cmd}", sudo=True, dryrun=self.debug)

        exec_in_netns(f"ip link set up dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_netns(f"ip addr add {self.config.extended.public_interface.address} dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_netns(f"ip route add default via {self.config.extended.public_interface.gateway} dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_default(f"ip link add veth-host type veth peer name veth-public")
        exec_in_default(f"ip link set veth-public netns {PUBLIC_NETNS_NAME}")
        exec_in_default(f"ip link add link {self.right_interface} name {self.config.extended.get_right_interface_name()} type vlan id {self.config.extended.right_vlan}")
        exec_in_default(f"brctl addbr {NETNS_RIGHT_BRIDGE_NAME}")
        exec_in_default(f"brctl addif {NETNS_RIGHT_BRIDGE_NAME} veth-host")
        exec_in_default(f"brctl addif {NETNS_RIGHT_BRIDGE_NAME} {self.config.extended.get_right_interface_name()}")
        exec_in_default(f"ip link set up dev {NETNS_RIGHT_BRIDGE_NAME}")
        exec_in_default(f"ip addr add {self.config.general.right_interface_address} dev {NETNS_RIGHT_BRIDGE_NAME}")
        exec_in_default(f"ip link set up dev {self.config.extended.get_right_interface_name()}")
        exec_in_default(f"ip link set up dev veth-host")
        exec_in_netns(f"ip addr add {self.config.extended.right_netns_address} dev veth-public")
        exec_in_netns(f"ip link set up dev veth-public")
        
        # Install iptables rules
        exec_in_netns(f"iptables -t nat -A POSTROUTING -o veth-public -j MASQUERADE")
        exec_in_default(f"iptables -t nat -A POSTROUTING -o {NETNS_RIGHT_BRIDGE_NAME} -j MASQUERADE")

        # Setup upstream links
        threads = []
        for mode in self.modes:
            mode.setup()
            t = Thread(target=mode.wait_for_initial_config, args=(), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
        
        for mode in self.modes:
            if not mode.is_ready():
                Logger.info(f"Unable to set up {mode.name}: No default gateway was found.")
        
        # Some hacky workaround: Add the VLAN interface again to the network namespace with a delay. 
        # Otherwise the interface has lost its physical interface mapping in the netns.
        exec_in_netns(f"ip link del {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_default(f"ip link add link {self.left_interface} name {self.config.extended.public_interface.get_public_interface_name()} type vlan id {self.config.extended.public_interface.vlan}")
        exec_in_default(f"ip link set dev {self.config.extended.public_interface.get_public_interface_name()} netns {PUBLIC_NETNS_NAME}")
        exec_in_netns(f"ip link set up dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_netns(f"ip addr add {self.config.extended.public_interface.address} dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_netns(f"ip route add default via {self.config.extended.public_interface.gateway} dev {self.config.extended.public_interface.get_public_interface_name()}")
        exec_in_netns(f"iptables -t nat -A PREROUTING -i {self.config.extended.public_interface.get_public_interface_name()} -p tcp -j DNAT --to-destination {self.config.general.right_endpoint_ip}")
        exec_in_netns(f"iptables -t nat -A PREROUTING -i {self.config.extended.public_interface.get_public_interface_name()} -p udp -j DNAT --to-destination {self.config.general.right_endpoint_ip}")


    def cleanup_old_config(self) -> None:
        # Cleanup upstream links
        for mode in self.modes:
            mode.cleanup_config()

        # Cleanup left interface
        run_log_on_error(f"ip link del {self.config.extended.get_left_interface_name()}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        
        # Delete iptables rules (network namespace will be cleaned by deletion)
        run_log_on_error(f"iptables -t nat -D POSTROUTING -o {NETNS_RIGHT_BRIDGE_NAME} -j MASQUERADE", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)

        # Cleanup backrouting interfaces and namespace
        run_log_on_error(f"ip netns del {PUBLIC_NETNS_NAME}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link set down dev {NETNS_RIGHT_BRIDGE_NAME}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"brctl delbr {NETNS_RIGHT_BRIDGE_NAME}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link del veth-host", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link del veth-public", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link del {self.config.extended.public_interface.get_public_interface_name()}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link del {self.config.extended.get_right_interface_name()}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)


class RealpathModeEntry(Mode):
    def __init__(self, config: RealNetworkEntry, base_interface: str, 
                 left_vlan_interface: str, maingui, debug: bool = False,):
        super().__init__(None, maingui, debug)

        self.name = config.name
        self.config = config
        self.interface_name = config.get_interface_name()
        self.left_vlan_interface = left_vlan_interface
        self.vlan = config.vlan
        self.base_interface = base_interface
        self.default_gateway: Optional[str] = None
        self.fwmark = config.vlan

    def add_tabs(self, window) -> None:
        frame = ttk.Frame(window.get_tabs())
        self.label = ttk.Label(frame, text=f"Real path via {self.name} is enabled.")
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        self.label.configure(font=('URW Gothic L', '28', 'bold'))
        window.add_tab(self.name, frame, self)
    
    def enable(self) -> None:
        if self.default_gateway is None:
            Logger.error(f"Cannot enable {self.name} without default gateway!")
            self.label.configure(text=f"{self.name} not enabled due to setup error.", foreground="red")
            return

        try:
            run_fail_on_error(f"iptables -t mangle -A PREROUTING -i {self.left_vlan_interface} -j MARK --set-mark {self.fwmark}", 
                              sudo=True, 
                              dryrun=self.debug)
            run_fail_on_error(f"ip rule add fwmark {self.fwmark} table {self.fwmark}", 
                              sudo=True, 
                              dryrun=self.debug)
            run_fail_on_error(f"conntrack -F", 
                              sudo=True, 
                              dryrun=self.debug)
        except Exception as ex:
            Logger.error(f"Unable to install required route: {ex}")

        Logger.info(f"Real path {self.name} enabled")

    def disable(self) -> None:
        if self.default_gateway is None:
            Logger.error(f"Cannot disable {self.name} without default gateway!")
            return

        try:
            run_fail_on_error(f"iptables -t mangle -D PREROUTING -i {self.left_vlan_interface} -j MARK --set-mark {self.fwmark}", 
                              sudo=True, 
                              dryrun=self.debug)
            run_fail_on_error(f"ip rule del fwmark {self.fwmark} table {self.fwmark}", 
                              sudo=True, 
                              dryrun=self.debug)
        except Exception as ex:
            Logger.error(f"Unable to remove route: {ex}")

        Logger.info(f"Real path {self.name} disbaled")

    def wait_for_initial_config(self) -> None:
        if self.debug:
            time.sleep(5)

            if self.name == "Starlink":
                time.sleep(5)
                return

            self.default_gateway = "1.1.1.1"
            return
        
        if self.config.gateway is not None:
            self.default_gateway = self.config.gateway
            time.sleep(5)
            return

        start = time.time()

        while time.time() < start + 10:
            try:
                self.default_gateway = RealpathModeEntry.get_default_gateway(self.interface_name)
            except Exception as ex:
                Logger.error(f"{self.name}: Interface {self.interface_name}: Unable to get gateway: {ex}")
                self.default_gateway = None
                return

            if self.default_gateway is not None:
                return
            
            time.sleep(0.5)
        
        Logger.error(f"{self.name}: Interface {self.interface_name}: Unable to get gateway in timeout")
    
    def is_ready(self) -> bool:
        if self.default_gateway is not None:
            Logger.info(f"Got default gateway for {self.name}: {self.default_gateway}")
            run_fail_on_error(f"ip route add default via {self.default_gateway} dev {self.interface_name} table {self.fwmark}", 
                              sudo=True, 
                              dryrun=self.debug)
            return True
        else:
            return False

    def cleanup_config(self) -> None:
        run_log_on_error(f"iptables -t nat -D POSTROUTING -o {self.interface_name} -j MASQUERADE", sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"iptables -t mangle -D PREROUTING -i {self.left_vlan_interface} -j MARK --set-mark {self.fwmark}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip rule del fwmark {self.fwmark} table {self.fwmark}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip route del default via {self.default_gateway} dev {self.interface_name} table {self.fwmark}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)
        run_log_on_error(f"ip link del {self.interface_name}", 
                         sudo=True, 
                         dryrun=self.debug, 
                         log_debug=True)

    def setup(self) -> None:
        run_fail_on_error(f"ip link add link {self.base_interface} name {self.interface_name} type vlan id {self.vlan}", 
                          sudo=True, 
                          dryrun=self.debug)
        run_fail_on_error(f"ip link set up dev {self.interface_name}", 
                          sudo=True, 
                          dryrun=self.debug)
        
        if self.config.address is not None:
            run_fail_on_error(f"ip address add {self.config.address} dev {self.interface_name}", 
                              sudo=True,
                              dryrun=self.debug)
            run_fail_on_error(f"ip route add default via {self.config.gateway} dev {self.interface_name}", 
                              sudo=True,
                              dryrun=self.debug)
            

        run_fail_on_error(f"iptables -t nat -A POSTROUTING -o {self.interface_name} -j MASQUERADE", 
                          sudo=True, 
                          dryrun=self.debug)

    @staticmethod
    def get_default_gateway(interface: str) -> str | None:
        try:
            result = subprocess.run(
                ['ip', 'route', 'show', 'dev', interface],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                return None

            for line in result.stdout.splitlines():
                if line.startswith('default'):
                    parts = line.split()
                    if 'via' in parts:
                        gateway_index = parts.index('via') + 1
                        return parts[gateway_index]
            return None

        except Exception as e:
            print(f"Exception: {e}")
            return None
