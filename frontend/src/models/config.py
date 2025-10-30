import json
from dataclasses import dataclass, field
from typing import List, Optional

from constants import *


@dataclass
class RealNetworkEntry:
    name: str
    vlan: int
    address: Optional[str]
    gateway: Optional[str]

    def get_interface_name(self) -> str:
        return f"vlan{self.vlan}-d"


@dataclass
class PublicInterface:
    address: str
    gateway: str
    vlan: int

    def get_public_ip(self) -> str:
        return self.address.split("/")[0]
    
    def get_public_interface_name(self) -> str:
        return f"vlan{self.vlan}-d"


@dataclass
class ExtendedConfig:
    left_vlan: int
    right_vlan: int
    public_interface: PublicInterface
    right_netns_address: str
    configs: List[RealNetworkEntry] = field(default_factory=list)

    def get_right_interface_name(self) -> str:
        return f"{RIGHT_INTERFACE}.{self.right_vlan}"
    
    def get_left_interface_name(self) -> str:
        return f"{LEFT_INTERFACE}.{self.left_vlan}"


@dataclass
class GeneralConfig:
    left_endpoint_ip: str
    right_endpoint_ip: str
    left_interface_address: str
    right_interface_address: str


@dataclass
class FullConfig:
    general: GeneralConfig
    extended: ExtendedConfig

    @staticmethod
    def from_json_file(path: str) -> "FullConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # General
        general = GeneralConfig(**data["general"])

        # Public Interface
        pub_intf = PublicInterface(**data["extended"]["public_interface"])

        # Extended
        configs = [RealNetworkEntry(**cfg) for cfg in data["extended"]["configs"]]
        extended = ExtendedConfig(
            left_vlan=data["extended"]["left_vlan"],
            right_vlan=data["extended"]["right_vlan"],
            public_interface=pub_intf,
            right_netns_address=data["extended"]["right_netns_address"],
            configs=configs,
        )

        return FullConfig(general=general, extended=extended)

    def __str__(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)
