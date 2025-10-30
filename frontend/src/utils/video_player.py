import cv2
import os

from tkinter import ttk
from PIL import Image, ImageTk

from utils.logger import Logger


class VideoPlayer:
    def __init__(self, frame, video_path, height, width):
        self.video_path = video_path
        self.height = height
        self.width = width
        self.label = ttk.Label(frame)
        self.label.pack()

        try:
            if not os.path.isfile(video_path):
                raise Exception("Video file not found.")

            self.cap = cv2.VideoCapture(video_path)
        except Exception as ex:
            Logger.error(f"Unable to open Video file: {video_path}: {ex}")
            self.cap = None

    def __del__(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

        self.label.destroy()
    
    def update(self, secs: int) -> None:
        if self.cap is None:
            return

        self.cap.set(cv2.CAP_PROP_POS_MSEC, secs * 1000)
        ret, frame = self.cap.read()

        if not ret or frame is None:
            return

        frame =  cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)

        image = image.resize((self.width, self.height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image=image)

        self.label.config(image=photo)
        self.label.image = photo
