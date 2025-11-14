#!/usr/bin/python3
#
# This file is part of Emulation Demonstrator.
#
# Copyright (C) 2025  Martin Ottens
# 
# This program is free software: you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License 
# along with this program. If not, see https://www.gnu.org/licenses/.
#

import argparse
import tkinter as tk
import os

from typing import List
from threading import Thread

from gui import EmulationDemonstrator
from utils.logger import *
from modes.passthrough import PassthroughMode
from modes.emulator import EmulatorMode
from modes.realpath import RealpathMode
from constants import RIGHT_INTERFACE, LEFT_INTERFACE
from models.operation import OperationMode
from models.config import *


def check_interfaces(names: List[str]) -> bool:
    existing_interfaces = os.listdir('/sys/class/net/')
    for name in names:
        if name not in existing_interfaces:
            return False
    return True


def clean(config: FullConfig, debug: bool = False) -> None:
    try:
        EmulatorMode.cleanup_old_config(config, RIGHT_INTERFACE, LEFT_INTERFACE, dryrun=debug)
    except Exception as ex:
        Logger.error(f"Unhandeled exception during interface cleanup: {ex}")

    realpath = RealpathMode(config, RIGHT_INTERFACE, LEFT_INTERFACE, None, debug)
    try:
        realpath.cleanup_old_config()
    except Exception as ex:
        Logger.error(f"Unhandeled exception during interface cleanup: {ex}")


def main(config: FullConfig, debug: bool = False, verbose: bool = False, 
         mode: OperationMode = OperationMode.ROUTED) -> None:
    root = tk.Tk()
    window = EmulationDemonstrator(root, debug)
    Logger.set_logger(window, root, verbose)

    if debug:
        Logger.warning("Tool is running in debug mode. No commands are executed.")

    if not debug and not check_interfaces([RIGHT_INTERFACE, LEFT_INTERFACE]):
        Logger.critical("Required Interfaces are not up.")
        window.run_mainloop()
        sys.exit(1)
    
    try:
        EmulatorMode.cleanup_old_config(config, RIGHT_INTERFACE, LEFT_INTERFACE, dryrun=debug)
    except Exception as ex:
        Logger.error(f"Unhandeled exception during interface cleanup: {ex}")


    if mode == OperationMode.ROUTED or mode == OperationMode.BRIDGED:
        try:
            EmulatorMode.config_interfaces(config, RIGHT_INTERFACE, LEFT_INTERFACE, 
                                           as_bridge=(mode == OperationMode.BRIDGED), 
                                           dryrun=debug)
        except Exception as ex:
            Logger.critical(f"Unable to set up interfaces: {ex}")
            window.run_mainloop()
            sys.exit(1)

        passthrough = PassthroughMode(config, window, debug, masquerade=False)
        emulator = EmulatorMode(config, RIGHT_INTERFACE, LEFT_INTERFACE, 
                                window, debug, masquerade=False)
        emulator.add_tabs(window)
        passthrough.add_tabs(window)
    elif mode == OperationMode.EXTENDED:
        window.show_init_screen("Waiting for interface configuration ...")
        realpath = RealpathMode(config, RIGHT_INTERFACE, LEFT_INTERFACE, window, debug)
        try:
            realpath.cleanup_old_config()
        except Exception as ex:
            Logger.error(f"Unhandeled exception during interface cleanup: {ex}")

        def config_interfaces_async():
            try:
                realpath.config_interfaces()

                def __event_submit(window):
                    window.stop_init_screen()
                
                window.add_async_event(__event_submit, window=window)
            except Exception as ex:
                Logger.critical(f"Unable to set up interfaces: {ex}")
        
        config_thread = Thread(target=config_interfaces_async)
        config_thread.start()

        passthrough = PassthroughMode(config, window, debug, masquerade=True)
        emulator = EmulatorMode(config, RIGHT_INTERFACE, LEFT_INTERFACE, window, 
                                debug, masquerade=True)
        emulator.add_tabs(window)
        passthrough.add_tabs(window)
        realpath.add_tabs(window)
    else:
        Logger.critical(f"Unknown operation mode: {mode}")
        window.run_mainloop()
        sys.exit(1)

    Logger.info("Demonstrator loaded.")
    window.run_mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Emulation Demonstrator")
    parser.add_argument("--debug", "-d", action="store_true", help="Local debug mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose log mode")
    parser.add_argument("--mode", "-m", type=str, choices=[str(OperationMode.BRIDGED), str(OperationMode.ROUTED), str(OperationMode.EXTENDED)],
                        required=True, help="Select operation mode for demonstrator")
    parser.add_argument("--clean", "-c", action="store_true", help="Clean interfaces and exit")
    parser.add_argument("CONFIG", type=str, help="Path to config.json")
    args = parser.parse_args()

    mode = OperationMode.from_str(args.mode)

    config = FullConfig.from_json_file(args.CONFIG)

    if args.clean:
        clean(config=config, debug=args.debug)
        sys.exit(0)

    main(config=config, 
         debug=args.debug, 
         verbose=args.verbose, 
         mode=mode)
