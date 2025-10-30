import json

from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from utils.utils import run_fail_on_error, invoke_subprocess
from utils.logger import Logger


class TheaterQContMode(Enum):
    HOLD = "HOLD"
    LOOP = "LOOP"
    CLEAN = "CLEAN"

    @staticmethod
    def from_str(string: str):
        try: return TheaterQContMode(string)
        except Exception:
            raise Exception(f"Unknown TheaterQContMode '{string}'")
        
    def __str__(self) -> str:
        return str(self.value)


class TheaterQStage(Enum):
    LOAD = "LOAD"
    RUN = "RUN"
    CLEAR = "CLEAR"
    FINISH = "FINISH"
    ARM = "ARM"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def from_str(string: str):
        try: return TheaterQStage(string)
        except Exception:
            raise Exception(f"Unknown TheaterQStage '{string}'")
        
    def __str__(self) -> str:
        return str(self.value)


@dataclass
class TheaterQDualLinkSettings:
    forward_trace: List[str]
    return_trace: List[str]
    contmode: TheaterQContMode

    def __str__(self) -> str:
        return f"TheaterQDualLinkSettings (forward={len(self.forward_trace)}, return={len(self.return_trace)}, mode={self.contmode})"


@dataclass
class TheaterQState:
    stage: TheaterQStage
    contmode: TheaterQContMode
    position_time: int
    position_count: int
    total_time: int
    total_count: int


class TheaterQHandler:
    __THEATERQ_INIT_TEMPLATE = "tc qdisc add dev {dev} root handle {handle} theaterq stage LOAD syncgroup {syncgroup} ingest EXTENDED"
    __THEATERQ_START_TEMPLATE = "tc qdisc change dev {dev} handle {handle} theaterq stage {runmode} cont {contmode}"
    __THEATERQ_PREP_TEMPLATE = "tc qdisc change dev {dev} handle {handle} theaterq cont {contmode}"
    __THEATERQ_STOP_TEMPLATE = "tc qdisc change dev {dev} handle {handle} theaterq stage CLEAR"
    __THEATERQ_REMOVE_TEMPLATE = "tc qdisc del dev {dev} root handle {handle}"
    __THEATERQ_INFO_TEMPLATE = "tc -j qdisc sh dev {dev} handle {handle}"

    def __init__(self, forward_interface: str, return_interface: str, 
                 syncgroup: int = 1, handle: int = 1, dryrun: bool = False) -> None:
        self.running = False
        self.settings: Optional[TheaterQDualLinkSettings] = None
        self.forward_interface = forward_interface
        self.return_interface = return_interface
        self.syncgroup = syncgroup
        self.handle = handle
        self.dryrun = dryrun

        self.clean()
        
        cmd = self.__THEATERQ_INIT_TEMPLATE.format(dev=self.forward_interface,
                                                   handle=self.handle,
                                                   syncgroup=self.syncgroup)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)

        cmd = self.__THEATERQ_INIT_TEMPLATE.format(dev=self.return_interface,
                                                   handle=self.handle,
                                                   syncgroup=self.syncgroup)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)
        
    def __del__(self) -> None:
        self.clean()
    
    def clean(self) -> None:
        if self.running:
            self.stop()

        cmd = self.__THEATERQ_REMOVE_TEMPLATE.format(dev=self.forward_interface,
                                                     handle=self.handle)
        try:
            invoke_subprocess(cmd, capture_output=True, sudo=True, dryrun=self.dryrun)
        except Exception: pass

        cmd = self.__THEATERQ_REMOVE_TEMPLATE.format(dev=self.return_interface,
                                                     handle=self.handle)
        try:
            invoke_subprocess(cmd, capture_output=True, sudo=True, dryrun=self.dryrun)
        except Exception: pass

    def __get_details(self, interface: str) -> TheaterQState:
        cmd = self.__THEATERQ_INFO_TEMPLATE.format(dev=interface, handle=self.handle)
        try:
            process = invoke_subprocess(cmd, capture_output=True, sudo=True, 
                                        dryrun=self.dryrun, log_debug=True)

            if process.returncode != 0:
                raise Exception("Qdisc show command failed.")
            
            if self.dryrun:
                return TheaterQState(stage=(TheaterQStage.RUN if self.settings is not None else TheaterQStage.CLEAR),
                                     contmode=(self.settings.contmode if self.settings is not None else TheaterQContMode.LOOP),
                                     position_count=100,
                                     position_time=100000000,
                                     total_count=1000,
                                     total_time=1000000000)
            
            data = json.loads(process.stdout.decode("utf-8"))

            for entry in data:
                if entry["kind"] == "theaterq" and entry["root"]:
                    options = entry["options"]
                    return TheaterQState(stage=options["stage"],
                                         contmode=options["cont_mode"],
                                         position_time=options["position_time"],
                                         position_count=options["position"],
                                         total_time=options["entries_time"],
                                         total_count=options["entries"])
            
            raise Exception("Unable to find theaterq qdisc.")

        except Exception as ex:
            raise Exception("Unable to retrieve qdisc stats!") from ex
        
    def __load_trace_file(self, interface: str, trace: List[str]) -> None:
        with open(f"/dev/theaterq:{interface}:{self.handle}:0", "w") as handle:
            for entry in trace:
                handle.write(entry + ("\n" if not entry.endswith("\n") else ""))
                handle.flush()

    def update(self, settings: TheaterQDualLinkSettings) -> None:
        if self.running or self.is_qdisc_running():
            self.stop()

        self.settings = settings

        if self.dryrun:
            Logger.debug(f"Update settings in dry run: {settings}")
            return

        try:
            self.__load_trace_file(self.forward_interface, settings.forward_trace)
            self.__load_trace_file(self.return_interface, settings.return_trace)
        except Exception as ex:
            raise Exception("Unable to load trace file") from ex

    def get_details(self) -> TheaterQState:
        forward_instance = self.__get_details(self.forward_interface)
        return_instance = self.__get_details(self.return_interface)

        entries = max(forward_instance.position_count, return_instance.position_count)
        time = max(forward_instance.position_time, return_instance.position_time)
        entries_total = max(forward_instance.total_count, return_instance.total_count)
        time_total = max(forward_instance.total_time, return_instance.total_time)

        return TheaterQState(stage=TheaterQStage.from_str(forward_instance.stage),
                             contmode=TheaterQContMode.from_str(forward_instance.contmode),
                             position_count=entries,
                             position_time=time,
                             total_count=entries_total,
                             total_time=time_total)

    def is_running(self) -> bool:
        return self.is_running

    def is_qdisc_running(self, fake: bool = False) -> bool:
        if fake:
            return False

        for interface in [self.forward_interface, self.return_interface]:
            status = self.__get_details(interface)
            if status.stage in [TheaterQStage.RUN, TheaterQStage.ARM, TheaterQStage.FINISH]:
                return True
            
        return False

    def stop(self) -> bool:
        if not self.running and not self.is_qdisc_running():
            return False
        
        cmd = self.__THEATERQ_STOP_TEMPLATE.format(dev=self.forward_interface, 
                                                   handle=self.handle)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)

        cmd = self.__THEATERQ_STOP_TEMPLATE.format(dev=self.return_interface, 
                                                   handle=self.handle)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)

        self.settings = None
        self.running = False
        return True

    def start(self, arm: bool = False) -> bool:
        if self.settings is None or self.running or self.is_qdisc_running(fake=self.dryrun):
            return False
        
        cmd = self.__THEATERQ_PREP_TEMPLATE.format(dev=self.return_interface,
                                                    handle=self.handle,
                                                    contmode=self.settings.contmode)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)

        # We are in a syncgroup, only start forward one, rest will follow.
        runmode = TheaterQStage.ARM if arm else TheaterQStage.RUN
        cmd = self.__THEATERQ_START_TEMPLATE.format(dev=self.forward_interface,
                                                    handle=self.handle,
                                                    contmode=self.settings.contmode,
                                                    runmode=runmode)
        run_fail_on_error(cmd, sudo=True, dryrun=self.dryrun)
        self.running = True
        
        return True
