import serial
import time

from threading import Thread, Event

from utils.logger import Logger


class SerialButton:
    def __init__(self, device: str):
        self.device = device
        self.thread = None
        self.stream = None

    def __reading_thread(self) -> None:
        while not self.stop_event.is_set():
            try:
                s = self.stream.read(1)
                if s.decode("ascii") == "1":
                    self.callback()
            except Exception as ex:
                Logger.error(f"Unable to access external button: {ex}")
                time.sleep(10)

    def start_listening(self, callback) -> None:
        self.callback = callback

        try:
            self.stream = serial.Serial(self.device, 115200, timeout=None)
        except Exception as ex:
            Logger.error(f"Unable to connect to external button: {ex}")
            return

        self.stop_event = Event()
        self.stop_event.clear()

        self.thread = Thread(target=self.__reading_thread, args=(), daemon=True)
        self.thread.start()

    def stop_listening(self) -> None:
        if self.thread is None:
            return

        self.stop_event.set()
        self.stream.close()
        self.thread.join()
        self.thread = None

    def set_led_status(self, status: bool) -> None: 
        if self.stream is None:
            return
        
        char = "+" if status else "-"
        try:
            self.stream.write(char.encode("ascii"))
            self.stream.flush()
        except Exception as ex:
            Logger.error(f"Unable to set external button LED: {ex}")
