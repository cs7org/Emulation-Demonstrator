from enum import Enum
from datetime import datetime
from tkinter import ttk

import tkinter as tk
import sys

from constants import THEME_COLOR

class LogLevel(Enum):
    ERROR = "error", "[ERROR]"
    WARNING = "warning", "[WARNING]"
    INFO = "info", "[INFO]"
    DEBUG = "debug", "[DEBUG]"
    CRITICAL = "critical", "[CRITICAL]"

    def __init__(self, typename: str, prefix: str):
        self._typename = typename
        self._prefix = prefix

    @property
    def typename(self) -> str:
        return self._typename

    @property
    def prefix(self) -> str:
        return self._prefix

    def __str__(self) -> str:
        return self._prefix

    @classmethod
    def from_str(cls, name: str):
        name = name.strip().lower()
        for level in cls:
            if level.typename == name or level.prefix.lower() == name:
                return level
        raise ValueError(f"Unknown LogLevel: {name!r}")
    
class Logger:
    __target = None
    __verbose = False
    __root = None

    @classmethod
    def set_logger(cls, target, root, verbose: bool = False) -> None:
        cls.__target = target
        cls.__root = root
        cls.__verbose = verbose

    @classmethod
    def log(cls, level: LogLevel, msg: str) -> None:
        if level == LogLevel.DEBUG and not cls.__verbose:
            return
        
        time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        logstr = f"{time} - {level.prefix}: {msg}\n"
        print(logstr, end="")

        if cls.__target is not None:
            def __event_submit(clazz, levelname, logstr):
                clazz.__target.log(levelname, logstr)

            cls.__target.add_async_event(__event_submit, 
                                         clazz=cls, 
                                         levelname=level.typename, 
                                         logstr=logstr)

    @classmethod
    def info(cls, msg: str) -> None:
        cls.log(LogLevel.INFO, msg)

    @classmethod
    def error(cls, msg: str) -> None:
        cls.log(LogLevel.ERROR, msg)

    @classmethod
    def warning(cls, msg: str) -> None:
        cls.log(LogLevel.WARNING, msg)

    @classmethod
    def debug(cls, msg: str) -> None:
        cls.log(LogLevel.DEBUG, msg)

    @classmethod
    def critical(cls, msg: str) -> None:
        cls.log(LogLevel.CRITICAL, msg)

        if cls.__root is not None:
            def __event_submit(clazz):
                dialog = tk.Toplevel(clazz.__root)
                dialog.configure(background=THEME_COLOR)
                dialog.title("Critical Error")
                dialog.geometry("1920x1080")
                dialog.transient(clazz.__root)
                dialog.grab_set()

                label = ttk.Label(dialog, text=msg + "\nEmulator needs to be restarted.")
                label.configure(font=('URW Gothic L', '20', 'bold'), foreground="orange red")
                label.pack(pady=10)

                ok_button = ttk.Button(dialog, text="Restart", width=10, command=lambda: sys.exit(1))
                ok_button.pack(pady=5)
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
                y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
                dialog.geometry(f"+{x}+{y}")

            cls.__target.add_async_event(__event_submit, 
                                        clazz=cls)
            
        else:
            sys.exit(1)
