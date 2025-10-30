#!/usr/bin/python3

import tkinter as tk
import subprocess
import threading
import time
import os
import signal

from tkinter import ttk

INPUT_DEV="/dev/video0"
UDP_TARGET="<RECEIVER_IP>:12345"


class StreamerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LNdW Webcam Controller")
        self.geometry("400x300")
        self.streaming = False
        self.process = None
        self.quality_var = tk.StringVar(value="native")
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.create_widgets()

    def on_exit(self):
        if self.streaming:
            self.stop_stream(update=False)
        self.destroy()

    def create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", font=("Helvetica", 15))
        style.configure("TRadiobutton", font=("Helvetica", 15))
        style.configure("Green.TButton", foreground="green", font=("Helvetica", 18, "bold"))
        style.configure("Red.TButton", foreground="red", font=("Helvetica", 18, "bold"))
        style.configure("Bold.TButton", font=("Helvetica", 18, "bold"))

        frame = ttk.LabelFrame(self, text="Stream Quality", padding=10)
        frame.pack(padx=15, pady=15, fill="x")

        ttk.Radiobutton(frame, text="Native Resolution 720p (4.7 Mbit/s)", variable=self.quality_var,
                        value="native", command=self.quality_changed, style="TRadiobutton").pack(anchor="w", pady=6)
        ttk.Radiobutton(frame, text="Reduced Resoltion 480p (2.0 Mbit/s)", variable=self.quality_var,
                        value="low", command=self.quality_changed, style="TRadiobutton").pack(anchor="w", pady=6)

        self.live_button = ttk.Button(self, text="LIVE", command=self.toggle_live, style="Green.TButton")
        self.live_button.pack(pady=15, fill="x", padx=40)

        self.resync_button = ttk.Button(self, text="RESYNC Livestream", command=self.resync, style="Bold.TButton")
        self.resync_button.pack(pady=10, fill="x", padx=40)

        self.update_live_button_style()

    def update_live_button_style(self):
        if self.streaming:
            self.live_button.config(text="STOP Livestream", style="Red.TButton")
        else:
            self.live_button.config(text="START Livestream", style="Green.TButton")

    def quality_changed(self):
        if self.streaming:
            self.restart_stream()

    def toggle_live(self):
        if self.streaming:
            self.stop_stream()
        else:
            self.start_stream()
        self.update_live_button_style()

    def resync(self):
        if not self.streaming:
            return

        self.stop_stream(update=False)
        self.start_stream(update=False)

    def start_stream(self, update: bool = True):
        if self.process:
            self.stop_stream()

        cmd = self.get_ffmpeg_command()

        def target():
            self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
            self.process.wait()
            self.process = None
            self.streaming = False
            print("Thread terminated")

        self.streaming = True
        threading.Thread(target=target, daemon=True).start()
        if update:
            self.update_live_button_style()

    def stop_stream(self, update: bool = True):
        if self.process and self.process.poll() is None:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired as ex:
                print(ex)
                self.process.kill()
            self.process = None

        self.streaming = False

        if update:
            self.update_live_button_style()

    def restart_stream(self):
        self.stop_stream()
        time.sleep(1)
        self.start_stream()

    def get_ffmpeg_command(self):
        if self.quality_var.get() == "native":
            return f"/usr/bin/ffmpeg -f v4l2 -i {INPUT_DEV} -c:v libx264 -f mpegts -an -g 1 -preset ultrafast -tune zerolatency -omit_video_pes_length 1 udp://{UDP_TARGET}"
        else:
            return f"/usr/bin/ffmpeg -f v4l2 -i {INPUT_DEV} -c:v libx264 -vf scale=854:480 -f mpegts -an -g 1 -preset ultrafast -tune zerolatency -omit_video_pes_length 1 udp://{UDP_TARGET}?pkt_size=1024"


if __name__ == "__main__":
    app = StreamerApp()
    app.mainloop()
