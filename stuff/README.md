# Tools for the LNdW 2025 Demo

`webcam.py` can be installed on the *camera* computer and wraps a ffmpeg process with a tkinter GUI. 
The *camera* computer transmits a UDP stream of a webcam to the *player* computer.
On the *player* computer, mplayer is used for playback of the stream.

## Preparation
Install dependencies (both computers):
```bash
sudo apt install -y ffmpeg mplayer python3 python3-tk
```
Adapt the constants `INPUT_DEV` and `UDP_TARGET` in `webcam.py` for your setup.


## Usage
### Camera Computer
```bash
python3 webcam.py
```

### Player Computer
```bash
mplayer -nocache -framedrop -nosound -vo sdl udp://@:12345
```
