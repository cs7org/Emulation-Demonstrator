import tkinter as tk
import queue

from tkinter import ttk
from typing import List, Optional

from utils.logger import LogLevel
from modes.mode import Mode
from constants import THEME_COLOR, VERSION, GIT_VERSION

class EmulationDemonstrator:
    def __init__(self, root, debug: bool = False):
        self.root = root
        self.queue = queue.Queue()
        self.root.title("Emulation Demonstrator")
        self.dialog = None

        if not debug:
            self.root.attributes("-fullscreen", True)

        self.root.geometry("1920x1080")
        self.root.resizable(False, False)
        self.root.tk.call('lappend', 'auto_path', './awthemes-10.4.0')
        self.root.tk.call('package', 'require', 'awdark')
        self.style = ttk.Style(self.root)
        self.style.theme_use("awdark")
        self.style.configure('TNotebook.Tab', font=('URW Gothic L', '22', 'bold'), padding=(8, 4))
        self.style.configure("TLabelframe.Label", font=('URW Gothic L', '20'))
        self.style.configure("R.TButton", font=('URW Gothic L', '16', 'bold'), padding=(10,5))
        self.style.configure("R.TRadiobutton", font=('URW Gothic L', '16', 'bold'), padding=(10,5))
        self.root.configure(background=THEME_COLOR)

        self.root.bind("<<UpdateQueue>>", self.__process_event_queue)

        self.__create_main_window()

    def __create_main_window(self):
        self.tab_control = ttk.Notebook(self.root)
        self.tab_control.place(relx=0, rely=0, relwidth=1, relheight=0.76)
        self.tabs: List[Mode] = []
        self.active: Optional[Mode] = None
        self.tab_control.bind("<<NotebookTabChanged>>", self.__on_tab_change)

        bottom_frame = ttk.LabelFrame(self.root, text="Log")
        bottom_frame.place(relx=0, rely=0.76, relwidth=1, relheight=0.24)

        self.log_frame = tk.Text(bottom_frame, font=('URW Gothic L', '14'), borderwidth=0)
        self.log_frame.place(relx=0.01, rely=0.01, relwidth=0.98, relheight=0.86)
        self.log_frame.tag_configure(LogLevel.ERROR.typename, foreground="orange red")
        self.log_frame.tag_configure(LogLevel.CRITICAL.typename, foreground="orange red")
        self.log_frame.tag_configure(LogLevel.WARNING.typename, foreground="orange")
        self.log_frame.tag_configure(LogLevel.INFO.typename, foreground="white")
        self.log_frame.tag_configure(LogLevel.DEBUG.typename, foreground="steel blue")
        self.log_frame.configure(state="disabled")
        self.log_frame.configure(wrap="word")

        git_version = "local build" if GIT_VERSION == "%%gitversion%%" else GIT_VERSION
        version_label = ttk.Label(bottom_frame, text=f"Emulation Demonstrator {VERSION} ({git_version})", anchor="ne", justify="right")
        version_label.place(relx=0.01, rely=0.88, relwidth=0.98, relheight=0.1)
        version_label.configure(font=('URW Gothic L', '12'))

    def __on_tab_change(self, event):
        selected_tab = event.widget.select()
        index = event.widget.index(selected_tab)
        new_tab = self.tabs[index]

        if self.active is not None:
            self.active.disable()
            self.active = None
        
        if new_tab is not None:
            new_tab.enable()
            self.active = new_tab

    def add_async_event(self, target, *args, **kwargs) -> None:
        self.queue.put((target, args, kwargs))
        try:
            self.root.event_generate("<<UpdateQueue>>", when="tail")
        except Exception as ex:
            print(ex)
    
    def __process_event_queue(self, event = None) -> None:
        while True:
            try:
                target, args, kwargs = self.queue.get_nowait()
            except queue.Empty:
                break
            else:
                target(*args, **kwargs)

    def get_tabs(self):
        return self.tab_control
    
    def add_tab(self, name, frame, mode: Mode) -> None:
        self.tab_control.add(frame, text=name)
        self.tabs.append(mode)
    
    def enable_first_tab(self) -> None:
        if len(self.tabs) == 0:
            raise ValueError("Cannt enable without tabs.")

        self.tabs[0].enable()
        self.active = self.tabs[0]

    def log(self, typename: str, msg: str) -> None:
        self.log_frame.configure(state="normal")
        self.log_frame.insert(tk.END, msg, typename)
        self.log_frame.configure(state="disabled")
        self.log_frame.see("end")

    def run_mainloop(self) -> None:
        self.root.mainloop()

    def show_init_screen(self, msg: str) -> None:
        self.dialog = tk.Toplevel(self.root)
        self.dialog.configure(background=THEME_COLOR)
        self.dialog.title("Starting")
        self.dialog.geometry("1920x1080")
        self.dialog.transient(self.root)
        self.dialog.grab_set()

        label = ttk.Label(self.dialog, text="Emulation Demonstrator is starting up:\n" + msg)
        label.configure(font=('URW Gothic L', '20', 'bold'))
        label.pack(pady=10)

    def stop_init_screen(self) -> None:
        def __event_submit(context):
            if context.dialog is not None:
                context.dialog.destroy()
                context.dialog = None
        
        self.add_async_event(__event_submit, context=self)
