from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import argparse
import json
import random
import time
import os
import requests
import cv2
import numpy as np
from Arlo import Arlo
from datetime import timedelta, date
# import detect
# import fasterrcnn
import azure
from my_oauth2client.service_account import ServiceAccountCredentials

# path to the firebase private key data used to authenticate at Google server
# Firebase Console -> 3 dots next to relevant project and click on settings
# -> tab service accounts -> generate new private key
SERVICE_ACCOUNT_JSON = "my_service_account.json"

with open("keys.json") as f:
    j = json.load(f)
    assert j["static_url"][:4] == "http" and j["static_url"][-1] != "/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")

    parser.add_argument("--interval", help="timeinterval in seconds between email server is checked", default=5)
    parser.add_argument("--threshold", help="threshold when a change of a pixel grey value is consided a 'change'",
                        default=20)
    parser.add_argument("--verbose", help="give more output", action="store_true")
    parser.add_argument("--test", help="image this is returned instead of a server request")
    args = parser.parse_args()

    arlo = Arlo(j["arlo_user"], j["arlo_password"])
    known_ids = []
    # if args.test:
    #     print("Test", args.test, "from cwd", os.getcwd(), "exists:", os.path.exists(args.test))
    #     frames = [cv2.imread(args.test)]
    #     recording = {"presignedContentUrl": "", "deviceId": "48B45A7BEAE01", "createdDate": "heute",}
    #
    #     analyze_frames_and_notify(frames, "http://dummy", recording, args.server, gui=args.gui)
    #     return

    while True:
        start = time.time()
        today = date.today().strftime("%Y%m%d")
        yesterday = (date.today()-timedelta(days=1)).strftime("%Y%m%d")
        try:
            library = arlo.GetLibrary(yesterday, today)
        except requests.exceptions.HTTPError:
            print("somebody else logged in, stopping camera for 5 min")
            time.sleep(300)
            continue
        print("library request took:", time.time()-start, "has:", len(library))
        with open("lastactive.txt", "w") as f_:
            f_.write(str(start))

        for recording in library:
            video_id = str(recording['localCreatedDate'])
            if video_id in known_ids:
                continue
            if len(known_ids) > 100:
                known_ids.pop(0)
            known_ids.append(video_id)

            stream = arlo.StreamRecording(recording['presignedContentUrl'])
            if not os.path.exists("videos"):
                os.makedirs("videos/")
            path = 'videos/' + video_id + ".mp4"
            with open(path, 'wb') as f_:
                for chunk in stream:
                    f_.write(chunk)
                f_.close()

            print('Downloaded', path, "from Device", recording["deviceId"])

            frames = getFrames(path)
            # def analyze_frames_and_notify(frames, path, recording, server, gui=False):
            # suspicious_frame = detect.hogDetector(frames, gui=args.gui)
            # suspicious_frame = fasterrcnn.check_images(frames)
            suspicious_frame = azure.check_images(frames)

            if suspicious_frame:
                status, txt = notify_client(recording, suspicious_frame, path=path)
                assert status == 200, "couldn't transmit picture. Error: " + str(txt)

            os.remove(path)
        time.sleep(10)


def getFrames(path, interval=1):
    """ extract some frames from a video

    :param path: storage location of video
    :param interval: a frame every interval seconds will be retrieved
    :return: a list of length no_frames with ndarrays of frames with shape (frame_height, frame_width)
    """

    # known bug in OpenCV 3, can't do video caputure from file
    # https://github.com/ContinuumIO/anaconda-issues/issues/121
    if cv2.__version__.startswith("2."):
        print("capturing video:", path)
        cap = cv2.VideoCapture(path)
        assert cap.isOpened(), "Couldn't open capture for " + path
        frames_count = int(cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))
        try:
            fps = int(round(cap.get(cv2.cv.CV_CAP_PROP_FPS), 0))
        except ValueError:  # could not retrieve fps
            fps = 24

        def getFrame(frame_id):
            success, f_ = cap.read(frame_id)
            assert success, "could not capture frame " + str(frame_id * fps) + "\n" + str(frame_id)
            return f_
    else:
        # this solution does not work on pythonanywhere as there is no imageio installed.
        from imageio import get_reader
        from skvideo.io import ffprobe

        vid = get_reader(path, "ffmpeg")
        videometadata = ffprobe(path)
        rates = videometadata['video']['@avg_frame_rate'].split("/")
        fps = int(rates[0]) // int(rates[1])
        frames_count = np.int(videometadata['video']['@nb_frames'])

        def getFrame(frame_id):
            return vid.get_data(frame_id)

    height, width, _ = getFrame(0).shape
    rate = fps * interval  # every rate-th frame is extracted
    no_frames = frames_count // rate  # so many frames will be extracted
    return [getFrame(n * rate) for n in range(no_frames)]


def notify_client(recording, suspicious_frame, path):
    """ send out a push notifications through firebase

    """

    names = {"48B45972DBDBD": "Freisitz", "48B45A7BEAE01": "Eingang", "48B45975D51D8": "Ruecksitz",
             "48B45A75EC0D3": "Pool", "48B45A7MEA79E": "Terasse"}
    video_info = {"path": path, "url": recording['presignedContentUrl'],
                  "name": names[recording["deviceId"]], "date": str(recording['createdDate'])}

    def _get_access_token():
        """Retrieve a valid access token that can be used to authorize requests.

        :return: Access token.
        """
        SCOPES = "https://www.googleapis.com/auth/firebase.messaging"
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_ACCOUNT_JSON, SCOPES)
        access_token_info = credentials.get_access_token()
        return access_token_info.access_token

    url = "https://fcm.googleapis.com/v1/projects/" + j["firebase_project_id"] + "/messages:send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _get_access_token()
    }
    imdir, imname = "../static/arlo/app_images", str(random.randint(0, 10)) + "last.jpg"
    impath = os.path.join(imdir, imname)
    if not os.path.exists(imdir):
        os.makedirs(imdir)
    cv2.imwrite(impath, suspicious_frame)

    video_info["image"] = j["static_url"] + "/arlo/app_images/" + imname
    print("saving to", impath, "on server", video_info["image"])
    json_ = {
        "message": {
            "topic": "news",
            "data": {
                "url": video_info["url"],
                "name": video_info["name"],
                "date": video_info["date"],
                "image": video_info["image"],
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            }
        }
    }
    r = requests.post(url, headers=headers, json=json_)
    return r.status_code, r.text


if __name__ == "__main__":
    main()
