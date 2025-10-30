import json
import os
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Dict, Tuple, List

from utils.logger import Logger
from utils.generic_data_provider import GenericDataProvider
from models.scenario import ScenarioConfig


class USBWatcher(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_created(self, event):
        self.app.update_scenarios()
    
    def on_deleted(self, event):
        self.app.update_scenarios()
    
    def on_modified(self, event):
        self.app.update_scenarios()


class USBDataProvider(GenericDataProvider):
    def __init__(self, available_callback):
        self.watch_path = "/media/root"
        self.callback = available_callback
        self.scenarios: Dict[str, Tuple[str, str]] = {}
        self.__start_usb_monitor()

    def update_scenarios(self) -> None:
        self.scenarios.clear()

        usb_path = self.get_base_path()
        if not usb_path:
            Logger.debug("USB drive status changed.")
            self.callback(False)
            return

        for file in os.listdir(usb_path):
            if file.endswith(".json"):
                path = os.path.join(usb_path, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        name = data["name"]
                        self.scenarios[name] = file, data["description"]
                except Exception as e:
                    Logger.error(f"Error while loading: {e}")
        
        self.callback(True)
        Logger.info(f"USB drive was detected, scenario path: {usb_path}")

    def get_scenario_list(self) -> List[str]:
        return self.scenarios.keys()
    
    def get_scenario_details(self, name: str) -> str:
        return self.scenarios[name][1]

    def get_base_path(self):
        if os.path.exists(self.watch_path):
            for entry in os.listdir(self.watch_path):
                usb_path = os.path.join(self.watch_path, entry)
                if os.path.isdir(usb_path):
                    scenarios_path = os.path.join(usb_path, "scenarios")
                    if os.path.exists(scenarios_path):
                        return scenarios_path
        return None

    def __start_usb_monitor(self) -> None:
        handler = USBWatcher(self)
        self.observer = Observer()

        if os.path.exists(self.watch_path):
            self.observer.schedule(handler, self.watch_path, recursive=True)

        self.observer.start()

        def monitor():
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.observer.stop()
            self.observer.join()

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def load_scenario_config(self, name: str) -> ScenarioConfig:
        basepath = self.get_base_path()
        filename = os.path.join(basepath, self.scenarios[name][0])

        with open(filename, "r") as handle:
            data = json.load(handle)

        config = ScenarioConfig(name=data["name"],
                                description=data["description"],
                                basepath=basepath,
                                trace_format=data["trace"]["format"],
                                forward_file=data["trace"]["forward"],
                                return_file=data["trace"]["return"],
                                video=data.get("video", None))
        return config
