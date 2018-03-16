from server import getFrames
import detect
import os
dir = "videos"
for file in os.listdir(dir):
    frames, frames_list = getFrames(dir + "/" + file)
    detect.hogDetector(frames_list, gui=True)
    suspicious = detect.getSuspiciousFrames(frames, gui=True)
