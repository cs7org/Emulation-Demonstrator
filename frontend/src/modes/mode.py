from abc import ABC, abstractmethod


from models.config import *

class Mode(ABC):
    def __init__(self, config: FullConfig, maingui, debug: bool = False):
        self.config = config
        self.maingui = maingui
        self.debug = debug

    @abstractmethod
    def add_tabs(self, window) -> None:
        pass
    
    @abstractmethod
    def enable(self) -> None:
        pass

    @abstractmethod
    def disable(self) -> None:
        pass
