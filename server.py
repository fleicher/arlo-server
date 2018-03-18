from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import argparse
import time
import os
import requests
import cv2
import numpy as np
import detect
from oauth2client.service_account import ServiceAccountCredentials

# path to the firebase private key data used to authenticate at Google server
# TODO(developer): adjust this path after you have downloaded the service account json file from here
# Firebase Console -> 3 dots next to relevant project and click on settings
# -> tab service accounts -> generate new private key
SERVICE_ACCOUNT_JSON = "my_service_account.json"
PROJECT_ID = "quickstart-android-419d5"


def main():
    from Arlo import Arlo
    from datetime import timedelta, date
    parser = argparse.ArgumentParser()
    parser.add_argument("user", help="username")
    parser.add_argument("pw")
    parser.add_argument("--server", help="store image files locally, otherwise provide a method for image upload")
    parser.add_argument("--interval", help="timeinterval in seconds between email server is checked", default=5)
    parser.add_argument("--threshold", help="threshold when a change of a pixel grey value is consided a 'change'",
                        default=20)
    parser.add_argument("--verbose", help="give more output", action="store_true")
    args = parser.parse_args()
    arlo = Arlo(args.user, args.pw)
    known_ids = []
    while True:
        start = time.time()
        today = date.today().strftime("%Y%m%d")
        yesterday = (date.today()-timedelta(days=7)).strftime("%Y%m%d")
        library = arlo.GetLibrary(yesterday, today)
        print("library request took:", time.time()-start)

        for recording in library:
            id = recording['uniqueId']
            if id in known_ids:
                continue
            if len(known_ids) > 100:
                known_ids.pop(0)
            known_ids.append(recording['uniqueId'])

            stream = arlo.StreamRecording(recording['presignedContentUrl'])
            path = 'videos/' + id + ".mp4"
            with open(path, 'wb') as f:
                for chunk in stream:
                    f.write(chunk)
                f.close()

            print('Downloaded', path)

            frames = getFrames(path)
            os.remove(path)
            suspicious_frame = detect.hogDetector(frames, gui=True)

            if suspicious_frame is not None:
                video_info = {"path": path, "url": recording['presignedContentUrl'],
                              "name": "cam", "date": str(recording['createdDate'])}
                status, txt = notify_client(video_info, suspicious_frame, args.server)
                assert status == 200, "couldn't transmit picture. Error: " + str(txt)
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
            success, f = cap.read(frame_id)
            assert success, "could not capture frame " + str(frame_id * fps) + "\n" + str(frame_id)
            return f
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


def notify_client(video_info, suspicious_frame, server_url=None):
    """ send out a push notifications through firebase

    :param video_info: dict with various info about the video
    :param suspicious_frame: numpy array with shape (height, width)
    :param server_url: if this script is running on a server, provide the path to where the images can be served from
                       otherwise use an online sharing service like cloudinary
    :return: Tuple (status code of request, status description)
    """

    def _get_access_token():
        """Retrieve a valid access token that can be used to authorize requests.

        :return: Access token.
        """
        SCOPES = "https://www.googleapis.com/auth/firebase.messaging"
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_ACCOUNT_JSON, SCOPES)
        access_token_info = credentials.get_access_token()
        return access_token_info.access_token

    url = "https://fcm.googleapis.com/v1/projects/" + PROJECT_ID + "/messages:send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _get_access_token()
    }
    imdir, imname = "images", "last.jpg"
    impath = os.path.join(imdir, imname)
    if not os.path.exists(imdir):
        os.makedirs(imdir)
    cv2.imwrite(impath, suspicious_frame)

    if server_url:
        video_info["image"] = server_url + "/" + imdir + "/" + imname
    else:
        import cloudinary.uploader
        import cloudinary
        response = cloudinary.uploader.unsigned_upload(impath, "upload_identifier1", cloud_name="insert_cloudname_here")
        video_info["image"] = response["url"]
    json = {
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

    r = requests.post(url, headers=headers, json=json)
    return r.status_code, r.text


if __name__ == "__main__":
    main()
