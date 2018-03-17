import server
import detect
import os
dir = "videos"
for file in os.listdir(dir):
    frames = server.getFrames(dir + "/" + file)
    detect.hogDetector(frames, gui=True)
    suspicious = detect.getSuspiciousFrames(frames, gui=True)
    video_info = {"path": "none", "url": "https://arlo.netgear.com/#/viewShared/331AB93130F30011_201803",
                  "name": "name", "date": "sometime"}
    server.notify_client(video_info, suspicious)