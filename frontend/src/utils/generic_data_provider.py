import json
import os

from typing import Dict, Tuple, List

from utils.logger import Logger
from models.scenario import ScenarioConfig


class GenericDataProvider:
    def __init__(self, available_callback):
        self.callback = available_callback
        self.sample_path = "../../samples/scenarios"
        self.scenarios: Dict[str, Tuple[str, str]] = {}

    def update_scenarios(self) -> None:
        self.scenarios.clear()

        for file in os.listdir(self.sample_path):
            if file.endswith(".json"):
                path = os.path.join(self.sample_path, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        name = data["name"]
                        self.scenarios[name] = file, data["description"]
                except Exception as e:
                    Logger.error(f"Error while loading: {e}")
        
        self.callback(True)
        Logger.info(f"Loaded sample scenarios from: {self.sample_path}")

    def get_scenario_list(self) -> List[str]:
        return self.scenarios.keys()
    
    def get_scenario_details(self, name: str) -> str:
        return self.scenarios[name][1]

    def get_base_path(self):
        return self.sample_path

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
                                video=data["video"])
        return config
