import tkinter as tk
import matplotlib.pyplot as plt
import time

from tkinter import ttk
from threading import Thread, Event, Lock
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from modes.mode import Mode
from utils.logger import Logger
from utils.usb_data_provider import USBDataProvider
from utils.generic_data_provider import GenericDataProvider
from models.scenario import ScenarioConfig
from utils.theaterq import *
from utils.video_player import VideoPlayer
from constants import *
from utils.utils import run_fail_on_error, run_log_on_error
from models.config import *


# LAYOUT OVERVIEW
#
#  Replay Control     | Trace File Viz
# --------------------+---------------------
#  Scenario Selection | Simualtion Vide
#
class EmulatorMode(Mode):
    def __init__(self, config: FullConfig, interface_right: str, interface_left: str, 
                 maingui, debug: bool = False, masquerade: bool = False):
        super().__init__(config, maingui, debug)

        self.interface_right = interface_right
        self.interface_left = interface_left
        self.masquerade = masquerade

        self.replay_time = None
        self.replay_status = None
        self.replay_name = None
        self.replay_description = None
        self.play_button = None
        self.stop_button = None
        self.arm_button = None
        self.mode_var = None

        self.scenario_list = None
        self.scenario_name = None
        self.scenario_description = None
        self.load_button = None
        self.select_loop = None
        self.select_hold = None

        self.preview_scenario = None
        self.provider = None
        self.scenario: Optional[ScenarioConfig] = None
        self.current_time = 0
        self.contmode = TheaterQContMode.LOOP
        self.handler: Optional[TheaterQHandler] = None

        self.update_thread = None
        self.thread_event = None
        
        self.trace_var = None
        self.trace_plot_hint = None
        self.trace_plot_area = None
        self.canvas = None
        self.canvas_lock = Lock()
        self.trace_plot_return_file = False

        self.video_frame = None
        self.video_label = None
        self.video_player = None

        self.is_enabled = False
        self.is_playing = False
        
        self.debug_time = 0

    def add_tabs(self, window) -> None:
        frame = ttk.Frame(window.get_tabs())

        # REPLAY CONTROL
        scenario_info = ttk.LabelFrame(frame, text="Replay Control")
        scenario_info.place(relx=0.01, rely=0.02, relwidth=0.48, relheight=0.47)

        info_frame = ttk.Frame(scenario_info)
        info_frame.place(relx=0.01, rely=0.01, relwidth=0.98, relheight=0.8)

        time_frame = ttk.Frame(info_frame)
        time_frame.place(relx=0, rely=0.05, relwidth=0.4, relheight=0.15)
        time_label = ttk.Label(time_frame, text="Time: ")
        time_label.pack(side="left")
        time_label.configure(font=('URW Gothic L', '20'))
        self.replay_time = ttk.Label(time_frame, text="00:00 / 00:00")
        self.replay_time.pack(side="left")
        self.replay_time.configure(font=('URW Gothic L', '20', 'bold'))

        status_frame = ttk.Frame(info_frame)
        status_frame.place(relx=0.72, rely=0.05, relwidth=0.4, relheight=0.15)
        status_label = ttk.Label(status_frame, text="Status: ")
        status_label.pack(side="left")
        status_label.configure(font=('URW Gothic L', '20'))
        self.replay_status = ttk.Label(status_frame, text="Inactive", foreground="red")
        self.replay_status.pack(side="left")
        self.replay_status.configure(font=('URW Gothic L', '20', 'bold'))

        name_frame = ttk.Frame(info_frame)
        name_frame.place(relx=0, rely=0.25, relwidth=1, relheight=0.15)
        scenario_label = ttk.Label(name_frame, text="Scenario: ")
        scenario_label.pack(side="left")
        scenario_label.configure(font=('URW Gothic L', '20'))
        self.replay_name = ttk.Label(name_frame, text="Not loaded")
        self.replay_name.pack(side="left")
        self.replay_name.configure(font=('URW Gothic L', '20', 'bold'))

        self.replay_description = tk.Text(info_frame, font=('URW Gothic L', '14'), borderwidth=0)
        self.replay_description.place(relx=0, rely=0.45, relwidth=1, relheight=0.5)
        self.replay_description.insert(tk.END, "Select a scenario using the menu below.")
        self.replay_description.configure(state="disabled", wrap="word")

        control_frame = ttk.Frame(scenario_info)
        control_frame.place(relx=0, rely=0.81, relwidth=1, relheight=0.18)
        self.play_button = ttk.Button(control_frame, text="PLAY", style="R.TButton", 
                             command=self.__play_button)
        self.play_button.configure(state="disabled")
        self.play_button.grid(row=0, column=0, padx=5, sticky="ew")
        self.arm_button = ttk.Button(control_frame, text="ARM", style="R.TButton", 
                             command=self.__arm_button)
        self.arm_button.configure(state="disabled")
        self.arm_button.grid(row=0, column=1, padx=5, sticky="ew")
        self.stop_button = ttk.Button(control_frame, text="STOP", style="R.TButton",
                             command=self.__stop_button)
        self.stop_button.configure(state="disabled")
        self.stop_button.grid(row=0, column=2, padx=5, sticky="ew")
        self.mode_var = tk.StringVar(value=TheaterQContMode.LOOP)
        self.select_loop = ttk.Radiobutton(control_frame, text="Loop Scenario", 
                                  variable=self.mode_var, value=TheaterQContMode.LOOP, 
                                  style="R.TRadiobutton", command=self.__cont_mode_change)
        self.select_loop.grid(row=0, column=3, padx=5, sticky="ew")
        self.select_hold = ttk.Radiobutton(control_frame, text="Hold last value", 
                                  variable=self.mode_var, value=TheaterQContMode.HOLD, 
                                  style="R.TRadiobutton", command=self.__cont_mode_change)
        self.select_hold.grid(row=0, column=4, padx=5, sticky="ew")

        # SCENARIO SELECTION
        scenario_select = ttk.LabelFrame(frame, text="Scenario Selection")
        scenario_select.place(relx=0.01, rely=0.52, relwidth=0.48, relheight=0.47)

        self.scenario_list = tk.Listbox(scenario_select, font=('URW Gothic L', '14'), borderwidth=0)
        self.scenario_list.place(relx=0.01, rely=0.01, relwidth=0.4, relheight=0.96)
        self.scenario_list.bind("<<ListboxSelect>>", self.__scenario_view_changed)

        name_frame = ttk.Frame(scenario_select)
        name_frame.place(relx=0.42, rely=0, relwidth=0.57, relheight=0.2)
        self.scenario_name = ttk.Label(name_frame, text="Not available")
        self.scenario_name.pack(side="left")
        self.scenario_name.configure(font=('URW Gothic L', '18', 'bold'))

        self.scenario_description = tk.Text(scenario_select, font=('URW Gothic L', '13'), borderwidth=0)
        self.scenario_description.place(relx=0.42, rely=0.18, relwidth=0.57, relheight=0.58)
        self.scenario_description.insert(tk.END, "Insert a USB drive to show Scenarios.")
        self.scenario_description.configure(state="disabled", wrap="word")

        load_frame = ttk.Frame(scenario_select)
        load_frame.place(relx=0.42, rely=0.8, relwidth=0.57, relheight=0.18)
        self.load_button = ttk.Button(load_frame, text="Load Selected Scenario", style="R.TButton", 
                            command=self.__load_button)
        self.load_button.config(state="disabled")
        self.load_button.pack(expand=True)

        # TRACE FILE VIZ
        self.trace_plot_area = ttk.LabelFrame(frame, text="Trace File Graph")
        self.trace_plot_area.place(relx=0.5, rely=0.02, relwidth=0.49, relheight=0.47)
        self.trace_var = tk.StringVar(value="forward")
        control = ttk.Radiobutton(self.trace_plot_area, text="Show Forward Path Trace File", variable=self.trace_var, 
                                  value="forward", style="R.TRadiobutton", command=self.__viz_mode_changed)
        control.grid(row=0, column=1, padx=5, sticky="ew")
        control = ttk.Radiobutton(self.trace_plot_area, text="Show Return Path Trace File", variable=self.trace_var, 
                                  value="return", style="R.TRadiobutton", command=self.__viz_mode_changed)
        control.grid(row=0, column=2, padx=5, sticky="ew")
        self.trace_plot_hint = ttk.Label(self.trace_plot_area, text="Not available.")
        self.trace_plot_hint.place(relx=0.5, rely=0.5, anchor="center")
        self.trace_plot_hint.configure(font=('URW Gothic L', '20'))

        # SIMULATION VIDEO
        video_area = ttk.LabelFrame(frame, text="Simulation Visualization")
        video_area.place(relx=0.5, rely=0.52, relwidth=0.49, relheight=0.47)
        self.video_frame = ttk.Frame(video_area, width=720, height=300)
        self.video_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.video_label = ttk.Label(video_area, text="Not available.")
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")
        self.video_label.configure(font=('URW Gothic L', '20'))

        self.provider: GenericDataProvider = False
        if self.debug:
            self.provider = GenericDataProvider(self.usb_handler_changed)
        else:
            self.provider = USBDataProvider(self.usb_handler_changed)

        window.add_tab("Emulator", frame, self)
        self.provider.update_scenarios()

    @staticmethod
    def full_replace_textbox(textbox, new: str) -> None:
        textbox.configure(state="normal")
        textbox.delete("1.0", tk.END)
        textbox.insert(tk.END, new)
        textbox.configure(state="disabled")

    @staticmethod
    def usb_handler_changed_internal(context, status: bool) -> None:
        context.scenario_list.delete(0, tk.END)
        context.preview_scenario = None
        context.stop(unload=True)

        if status:
            context.scenario_name.configure(text="Select a Scenario")
            context.full_replace_textbox(context.scenario_description, "Please select a Scenario from the list.")
            all = context.provider.get_scenario_list()
            for entry in all:
                context.scenario_list.insert(tk.END, entry)
        else:
            context.scenario_name.configure(text="Not available")
            context.full_replace_textbox(context.scenario_description, "Insert a USB drive to show Scenarios.")

    def usb_handler_changed(self, status: bool) -> None:
        self.maingui.add_async_event(EmulatorMode.usb_handler_changed_internal, 
                                     context=self, 
                                     status=status)

    @staticmethod
    def state_change_callback(context, time_total: int, time_current: bool,
                              stage: TheaterQStage) -> None:
        status_text = "Inactive"
        status_color = "red"
        time_total_out = 0
        time_current_out = 0

        match stage:
            case TheaterQStage.UNKNOWN:
                time_total_out = time_total
                time_current_out = time_current
            case TheaterQStage.FINISH:
                status_text = "Active"
                status_color = "green"
                time_total_out = time_total
                time_current_out = time_current
                context.stop_button.configure(state="normal")
            case TheaterQStage.ARM:
                status_text = "Armed"
                status_color = "orange"
                time_total_out = time_total
                time_current_out = time_current
                context.stop_button.configure(state="normal")
            case TheaterQStage.RUN:
                status_text = "Active"
                status_color = "green"
                time_total_out = time_total
                time_current_out = time_current
                context.stop_button.configure(state="normal")

        context.replay_status.configure(text=status_text, foreground=status_color)

        def ns_to_time(ns: int) -> str:
            seconds = int(ns / (1000 * 1000 * 1000))
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{minutes:02}:{secs:02}"
        
        context.replay_time.configure(text=f"{ns_to_time(time_current_out)} / {ns_to_time(time_total_out)}")
        context.current_time = float(time_current_out) / (1000.0 * 1000.0 * 1000.0)

        if context.canvas is not None:
            context.trace_plot_update_marker(context.current_time)

        if context.video_player is not None:
            context.video_player.update(context.current_time)

    def __update_event_thread_fn(self) -> None:
        while True:
            if self.thread_event.is_set() or self.handler is None:
                return
            
            if self.debug:
                state = self.handler.get_details()
                self.maingui.add_async_event(EmulatorMode.state_change_callback,
                                             context=self, 
                                             time_total=100 * 1000 * 1000 * 1000, 
                                             time_current=self.debug_time * 1000 * 1000 * 1000, 
                                             stage=state.stage)
                self.debug_time += 1
                if self.debug_time >= 100:
                    if self.handler.settings.contmode == TheaterQContMode.HOLD:
                        self.debug -= 1
                    else:
                        self.debug_time = 0
            else:
                try:
                    state = self.handler.get_details()
                    self.maingui.add_async_event(EmulatorMode.state_change_callback,
                                                context=self, 
                                                time_total=state.total_time, 
                                                time_current=state.position_time, 
                                                stage=state.stage)
                except Exception as ex:
                    Logger.warning(f"Unable to update replay feedback: {ex}")

            time.sleep(1)

    def trace_plot_init_draw(self) -> None:
        if self.scenario is None:
            return
        
        trace = self.scenario.get_plot_data(self.trace_plot_return_file)
        self.trace_plot_hint.place_forget()

        self.fig, self.ax = plt.subplots(figsize=(9.3, 2.8))
        self.ax.plot(trace.time, trace.delay, label="Delay", color="royalblue")
        self.ax.set_xlabel("Simulation Time (s)", color="white")
        self.ax.set_ylabel("Delay (ms)", color="royalblue")
        self.ax.set_xlim(0, max(trace.time))
        self.ax.set_ylim(0)
        self.ax.tick_params(axis='y', labelcolor='royalblue')
        self.ax.tick_params(axis='x', labelcolor='white')
        self.ax.tick_params(axis='x', which='both', color='white')
        self.ax.tick_params(axis='y', which='both', color='white')

        for spine in self.ax.spines.values():
            spine.set_color('white')

        ax2 = self.ax.twinx()
        ax2.plot(trace.time, trace.rate, label="Rate", color="red")
        ax2.set_ylabel("Path Capacity (Mbps)", color="red")
        ax2.tick_params(axis='y', labelcolor='red')
        ax2.set_ylim(0, max(trace.rate) + 10)
        ax2.tick_params(axis='y', which='both', color='white')

        for spine in ax2.spines.values():
            spine.set_color('white')

        ax3 = self.ax.twinx()
        ax3.spines["right"].set_position(('outward', 50))
        ax3.spines["right"].set_visible(True)
        ax3.spines["right"].set_color("white")
        ax3.plot(trace.time, trace.queue, label='Queue Capacity', color='lawngreen')
        ax3.set_ylabel("Queue Capacity (pkts)", color='lawngreen')
        ax3.set_ylim(0)
        ax3.tick_params(axis='y', labelcolor='lawngreen', grid_color="white")
        ax3.tick_params(axis='y', which='both', color='white')

        for spine in ax3.spines.values():
            spine.set_color('white')

        self.marker = self.ax.axvline(x=self.current_time, color="orange", 
                                      linestyle="-", linewidth=4, label="Marker")
        self.fig.tight_layout()

        with self.canvas_lock:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.trace_plot_area)
            self.canvas.get_tk_widget().place(relx=0.5, rely=0.55, anchor="center")
            self.fig.patch.set_facecolor(THEME_COLOR)
            self.ax.set_facecolor(THEME_COLOR)
            self.canvas.get_tk_widget().config(bg=THEME_COLOR)

        self.idx = 0

    def trace_plot_update_marker(self, time: float) -> None:
        with self.canvas_lock:
            self.marker.set_xdata([time, time])
            self.canvas.draw_idle()

    def trace_plot_clear(self) -> None:
        if self.canvas is None:
            return

        with self.canvas_lock:
            self.trace_plot_hint.place(relx=0.5, rely=0.5, anchor="center")
            self.canvas.get_tk_widget().place_forget()
            plt.close(self.fig)
            self.canvas = None

    def start(self, arm: bool = False) -> None:
        self.load_button.configure(state="disabled")
        self.play_button.configure(state="disabled")
        self.arm_button.configure(state="disabled")
        self.select_loop.configure(state="disabled")
        self.select_hold.configure(state="disabled")
        theaterq_settings = TheaterQDualLinkSettings(self.scenario.forward_trace,
                                                     self.scenario.return_trace,
                                                     contmode=self.contmode)
        self.debug_time = 0

        try:
            self.handler.update(theaterq_settings)
            self.handler.start(arm)
        except Exception as ex:
            Logger.error(f"Unable to start TheaterQ replay: {ex}")
            self.stop()
            return

        self.thread_event = Event()
        self.thread_event.clear()
        self.update_thread = Thread(target=self.__update_event_thread_fn, daemon=True)
        self.update_thread.start()
        self.is_playing = True

    def stop(self, unload: bool = False) -> None:
        if self.thread_event is not None:
            self.thread_event.set()

        self.stop_button.configure(state="disabled")
        self.select_loop.configure(state="normal")
        self.select_hold.configure(state="normal")
        self.load_button.configure(state="normal")

        total_time = 0
        self.debug_time = 0
        if self.scenario is not None:
            total_time = self.scenario.get_length_ns()
        EmulatorMode.state_change_callback(self, total_time, 0, TheaterQStage.UNKNOWN)
        self.current_time = 0

        if self.handler is not None:
            try:
                self.handler.stop()
            except Exception as ex:
                Logger.error(f"Unable to stop TheaterQ replay: {ex}")

        if self.video_player is not None:
            self.video_player.update(0)

        self.is_playing = False

        if unload:
            self.trace_plot_clear()
            del self.video_player
            self.video_frame.place_forget()
            self.video_player = None
            self.video_label.place(relx=0.5, rely=0.5, anchor="center")
            self.scenario = None
            self.load_button.configure(state="disabled")
            self.play_button.configure(state="disabled")
            self.arm_button.configure(state="disabled")
            self.replay_name.configure(text="Not loaded")
            self.full_replace_textbox(self.replay_description, 
                                      "Select a Scenario using the menu below.")
            return
        
        self.play_button.configure(state="normal")
        self.arm_button.configure(state="normal")

    def __play_button(self) -> None:
        self.start(arm=False)

    def __arm_button(self) -> None:
        self.start(arm=True)

    def __stop_button(self) -> None:
        self.stop(unload=False)

    def __load_button(self) -> None:
        if self.preview_scenario is None:
            return

        self.play_button.configure(state="normal")
        self.arm_button.configure(state="normal")

        self.replay_name.configure(text=self.preview_scenario)
        self.full_replace_textbox(self.replay_description, 
                                  self.provider.get_scenario_details(self.preview_scenario))

        self.scenario = self.provider.load_scenario_config(self.preview_scenario)

        if self.canvas is not None:
            self.trace_plot_clear()
        
        if self.video_player is not None:
            del self.video_player
            self.video_frame.place_forget()
            self.video_player = None
            self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        self.trace_plot_init_draw()

        if self.scenario.video is not None:
            self.video_label.place_forget()
            self.video_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.video_player = VideoPlayer(self.video_frame, self.scenario.video, height=300, width=720)

        EmulatorMode.state_change_callback(self,
                                           time_total=self.scenario.get_length_ns(), 
                                           time_current=0, 
                                           stage=TheaterQStage.UNKNOWN)

    def __cont_mode_change(self) -> None:
        self.contmode = TheaterQContMode(self.mode_var.get())

    def __scenario_view_changed(self, event) -> None:
        selection = self.scenario_list.curselection()
        if selection:
            name = self.scenario_list.get(selection[0])
            details = self.provider.get_scenario_details(name)
            self.scenario_name.configure(text=name)
            self.full_replace_textbox(self.scenario_description, details)
            self.preview_scenario = name
            self.load_button.configure(state="normal")

    def __viz_mode_changed(self) -> None:
        self.trace_plot_return_file = self.trace_var.get() == "return"
        self.trace_plot_clear()
        self.trace_plot_init_draw()
    
    def enable(self) -> None:
        self.is_enabled = True
        if self.masquerade:
            try:
                run_fail_on_error(f"iptables -t nat -A PREROUTING -i {self.config.extended.get_left_interface_name()} -d {self.config.extended.public_interface.get_public_ip()} -j DNAT --to-destination {self.config.general.right_endpoint_ip}", sudo=True, dryrun=self.debug)
                run_fail_on_error(f"conntrack -F", sudo=True, dryrun=self.debug)
            except Exception as ex:
                Logger.error(f"Unable to install iptables rule: {ex}")

        try:
            self.handler = TheaterQHandler(forward_interface=self.interface_right,
                                           return_interface=self.interface_left,
                                           dryrun=self.debug)
        except Exception as ex:
            Logger.error(f"Error preparing TheaterQ: {ex}")
            return

        Logger.info("Emulator enabled")

    def disable(self) -> None:
        self.is_enabled = False

        self.stop(unload=True)
        del self.handler
        self.handler = None

        if self.masquerade:
            try:
                run_fail_on_error(f"iptables -t nat -D PREROUTING -i {self.config.extended.get_left_interface_name()} -d {self.config.extended.public_interface.get_public_ip()} -j DNAT --to-destination {self.config.general.right_endpoint_ip}", sudo=True, dryrun=self.debug)
            except Exception as ex:
                Logger.error(f"Unable to remove iptables rule: {ex}")

        Logger.info("Emulator disabled")

    @staticmethod
    def cleanup_old_config(config: FullConfig, interface_right: str, 
                           interface_left: str, dryrun: bool = False) -> None:
        run_log_on_error(f"iptables -t nat -D PREROUTING -i {config.extended.get_left_interface_name()} -d {config.extended.public_interface.get_public_ip()} -j DNAT --to-destination {config.general.right_endpoint_ip}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"ip addr del {config.general.right_interface_address} dev {interface_right}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"ip addr del {config.general.left_interface_address} dev {interface_left}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"ip link set down dev {interface_right}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"ip link set down dev {interface_left}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"ip link set down dev {BRIDGE_MODE_BRIDGE_NAME}", sudo=True, dryrun=dryrun, log_debug=True)
        run_log_on_error(f"brctl delbr {BRIDGE_MODE_BRIDGE_NAME}", sudo=True, dryrun=dryrun, log_debug=True)

    @staticmethod
    def config_interfaces(config: FullConfig, interface_right: str, interface_left: str, 
                          as_bridge: bool = False, dryrun: bool = False) -> None:
        
        if not as_bridge:
            run_fail_on_error(f"ip addr add {config.general.right_interface_address} dev {interface_right}", sudo=True, dryrun=dryrun)
            run_fail_on_error(f"ip addr add {config.general.left_interface_address} dev {interface_left}", sudo=True, dryrun=dryrun)
        else:
            run_fail_on_error(f"brctl addbr {BRIDGE_MODE_BRIDGE_NAME}", sudo=True, dryrun=dryrun)
            run_fail_on_error(f"brctl addif {BRIDGE_MODE_BRIDGE_NAME} {interface_left}", sudo=True, dryrun=dryrun)
            run_fail_on_error(f"brctl addif {BRIDGE_MODE_BRIDGE_NAME} {interface_right}", sudo=True, dryrun=dryrun)
            run_fail_on_error(f"ip link set up dev {BRIDGE_MODE_BRIDGE_NAME}", sudo=True, dryrun=dryrun)
        
        run_fail_on_error(f"ip link set up dev {interface_right}", sudo=True, dryrun=dryrun)
        run_fail_on_error(f"ip link set up dev {interface_left}", sudo=True, dryrun=dryrun)
