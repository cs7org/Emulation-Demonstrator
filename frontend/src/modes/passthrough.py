import tkinter as tk

from tkinter import ttk

from modes.mode import Mode
from utils.logger import Logger
from utils.utils import run_fail_on_error
from constants import *
from models.config import *


class PassthroughMode(Mode):
    def __init__(self, config: FullConfig, maingui, debug: bool, masquerade: bool = False):
        super().__init__(config, maingui, debug)
        self.masquerade = masquerade

    def add_tabs(self, window) -> None:
        frame = ttk.Frame(window.get_tabs())
        label = ttk.Label(frame, text="Passthrough / Transparent Mode enabled.")
        label.place(relx=0.5, rely=0.5, anchor="center")
        label.configure(font=('URW Gothic L', '28', 'bold'))
        window.add_tab("Passthrough", frame, self)
    
    def enable(self) -> None:
        if self.masquerade:
            try:
                run_fail_on_error(f"iptables -t nat -A PREROUTING -i {self.config.extended.get_left_interface_name()} -d {self.config.extended.public_interface.get_public_ip()} -j DNAT --to-destination {self.config.general.right_endpoint_ip}", 
                                  sudo=True, 
                                  dryrun=self.debug)
                run_fail_on_error(f"conntrack -F", 
                                  sudo=True, 
                                  dryrun=self.debug)
            except Exception as ex:
                Logger.error(f"Unable to install iptables rule: {ex}")

        Logger.info("Passthrough enabled")

    def disable(self) -> None:
        if self.masquerade:
            try:
                run_fail_on_error(f"iptables -t nat -D PREROUTING -i {self.config.extended.get_left_interface_name()} -d {self.config.extended.public_interface.get_public_ip()} -j DNAT --to-destination {self.config.general.right_endpoint_ip()}", 
                                  sudo=True, 
                                  dryrun=self.debug)
            except Exception as ex:
                Logger.error(f"Unable to remove iptables rule: {ex}")

        Logger.info("Passthrough disbaled")
