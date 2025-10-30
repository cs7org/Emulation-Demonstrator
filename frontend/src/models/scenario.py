from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlotDataSeries:
    time: List[float] = field(default_factory=list)
    rate: List[int] = field(default_factory=list)
    delay: List[float] = field(default_factory=list)
    queue: List[int] = field(default_factory=list)


class ScenarioConfig:
    def __init__(self, name: str, description: str, basepath: str,
                 trace_format: str, forward_file: str, return_file: str,
                 video: Optional[str] = None):
        self.name = name
        self.description = description
        self.basepath = Path(basepath)
        self.trace_format = trace_format
        self.forward_file = self.basepath / forward_file
        self.return_file = self.basepath / return_file
        if video is None:
            self.video = None
        else:
            self.video = self.basepath / video

        if not self.forward_file.exists():
            raise Exception(f"Configured forward file does not exist: {self.forward_file}")
        
        if not self.return_file.exists():
            raise Exception(f"Configured return file does not exist: {self.return_file}")
        
        self.forward_trace = []
        with open(self.forward_file, "r") as handle:
            self.forward_trace = handle.readlines()
        
        self.return_trace = []
        with open(self.return_file, "r") as handle:
            self.return_trace = handle.readlines()

        if trace_format != "extended":
            self.return_trace = ScenarioConfig.extend_trace(self.return_trace)
            self.forward_trace = ScenarioConfig.extend_trace(self.forward_trace)

    def get_plot_data(self, return_trace: bool = False) -> PlotDataSeries:
        input = self.forward_trace if not return_trace else self.return_trace
        result = PlotDataSeries()
        t = 0
        for entry in input:
            if not entry[0].isdigit():
                continue

            keep, delay, _, rate, _, limit, _, _, _ = entry.replace("\n", "").split(",")
            t += int(keep)
            result.time.append(float(t) / (1000 * 1000)) # s
            result.delay.append(float(delay) / (1000 * 1000)) # ms
            result.rate.append(int(rate) // 1e6) # Mbps
            result.queue.append(int(limit)) # packets
        
        return result

    def get_length_ns(self) -> int:
        def get_one_len(file) -> int:
            result = 0
            for line in file:
                if not line[0].isdigit():
                    continue
                result += int(line.split(",")[0]) * 1000 # µs to ns
            
            return result
        
        return max(get_one_len(self.forward_trace), get_one_len(self.return_trace))
    
    def __str__(self) -> str:
        return f"{self.name} ({self.description})"
    
    @staticmethod
    def extend_trace(trace: List[str]) -> List[str]:
        result = []

        for entry in trace:
            if not entry[0].isnumeric():
                continue

            keep, latency, rate, loss, limit = entry.replace("\n", "").split(",")
            result.append(f"{keep},{latency},0,{rate},{loss},{limit},0,0,1\n")
        
        return result
