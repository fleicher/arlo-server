from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import argparse
import imaplib
import getpass
import email
import time
import re
import os
import requests
import shutil
import cv2
import numpy as np
import detect
# whole package is copied as no external packages can be installed on pythonanywhere
try:
    from my_oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    from oauth2client.service_account import ServiceAccountCredentials


# pattern of links in notification mails
PATTERN = "https://arlo\.netgear\.com/hmsweb/users/library/share/link/[A-F0-9_]+"
regex = re.compile(PATTERN)

# path to the firebase private key data used to authenticate at Google server
# TODO(developer): adjust this path after you have downloaded the service account json file from here
# Firebase Console -> 3 dots next to relevant project and click on settings
# -> tab service accounts -> generate new private key
SERVICE_ACCOUNT_JSON = "my_service_account.json"
PROJECT_ID = "quickstart-android-419d5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email", help="(G)mail account the Arlo notifications are sent to")
    parser.add_argument("--pw", help="Enter the pw here or when promted")
    parser.add_argument("--mailbox", help="mailbox in email account the notifications are sent to", default="INBOX")
    parser.add_argument("--imap", help="url of imap server", default='imap.gmail.com')
    parser.add_argument("--interval", help="timeinterval in seconds between email server is checked", default=5)
    parser.add_argument("--threshold", help="threshold when a change of a pixel grey value is consided a 'change'",
                        default=20)
    parser.add_argument("--verbose", help="give more output", action="store_true")
    args = parser.parse_args()

    M = imaplib.IMAP4_SSL(args.imap)
    M.login(args.email, args.pw if args.pw else getpass.getpass())
    if args.verbose:
        print("mailboxes:", M.list())

    while True:
        M.select(args.mailbox)
        rv, data = M.search(None, "ALL")
        if rv != 'OK':  # mail box is empty
            continue

        # iterate through new emails
        for num in data[0].split():
            rv, e_data = M.fetch(num, '(RFC822)')
            assert rv == 'OK', "could not retrieve message"

            email_html = ""
            email_parts = email.message_from_string(e_data[0][1].decode('utf-8'))
            for part in email_parts.walk():
                if part.get_content_type() != "text/html":
                    # collect all parts of the email that belong to the html body
                    continue
                binary_part = part.get_payload(decode=True)
                if binary_part:
                    email_html += binary_part.decode('utf-8')

            results = regex.findall(email_html)
            if not results:
                # list with Arlo URL as only entry if this email was by Arlo
                continue

            # mark email with link to be deleted on next pull of mailbox
            # M.store(num, "+FLAGS", "\\Deleted")

            if args.verbose:
                print("found email with link(s):", results)
            video_info = getVideo(results[0])
            if video_info is None:
                print("Couldn't retrieve Video, probably link already expired, so selenium couldn't load the page")
                continue
            frames = getFrames(video_info["path"])
            os.remove(video_info["path"])
            # suspicious = detect.getSuspiciousFrames(frames, args.threshold, gui=True)
            suspicious = detect.hogDetector(frames)

            if suspicious:
                if args.verbose:
                    print("Frames", suspicious, "are suspicious")
                status, txt = notify_client(video_info, frames[suspicious[0]])
                assert status == 200, "couldn't transmit picture. Error: " + str(txt)

        time.sleep(args.interval)
        if args.verbose:
            print("Check again in", args.interval, "seconds")


def getVideo(url, out_dir="videos"):
    """ use controlled browser to navigate to url provided in notification email and get real video url

    :param url: url provided in email
    :param out_dir: directory the video will be stored in (is created if doesn't exist yet)
    :return: None if video couldn't be retrieved, else: Dict: {"path": local path, "url": remote url, "name": camera name, "date": date as string}
    """
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException, NoSuchElementException
    from pyvirtualdisplay import Display

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    out_path = os.path.join(out_dir, os.path.basename(url) + ".mp4")
    with Display():
        # create virtual display so that selenium can run in terminal
        try:
            driver = webdriver.Firefox()
        except WebDriverException:
            driver = webdriver.Chrome()
        try:
            driver.get(url)
            with open("source.txt", "wb") as f:
                f.write(driver.page_source.encode("utf-8"))
            video_elem = driver.find_element_by_id("recordedVideo")
            source_elem = video_elem.find_element_by_tag_name("source")
            video_url = source_elem.get_attribute("src")

            side_elem = driver.find_element_by_class_name("shared-media-head")
            div0, div1 = side_elem.find_elements_by_tag_name("div")
            camera_name = div0.get_attribute("innerHTML")
            date = div1.get_attribute("innerHTML")

        except NoSuchElementException:
            driver.close()
            return None
        print("saving video from", video_url, "at", out_path)
        driver.close()
    req = requests.get(video_url, stream=True)
    with open(out_path, "wb") as f:
        assert req.status_code == 200
        shutil.copyfileobj(req.raw, f)
    return {"path": out_path, "url": video_url, "name": camera_name, "date": date}


def getFrames(path, interval=1):
    """ extract some frames from a video

    :param path: storage location of video
    :param interval: a frame every interval seconds will be retrieved
    :return: a list of length no_frames with ndarrays of frames with shape (frame_height, frame_width)
    """

    # known bug in OpenCV 3, can't do video caputure from file
    # https://github.com/ContinuumIO/anaconda-issues/issues/121
    if cv2.__version__.startswith("2."):
        cap = cv2.VideoCapture(path)
        assert cap.isOpened(), "Couldn't open capture for " + path
        fps = int(round(cap.get(cv2.cv.CV_CAP_PROP_FPS), 0))
        frames_count = cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)

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


def notify_client(video_info, suspicious_frame):
    """ send out a push notifications through firebase

    :param video_info: dict with various info about the video
    :param suspicious_frame: numpy array with shape (height, width)
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
    from matplotlib.pyplot import imsave
    # import base64

    # frame_small = suspicious_frame[::15, ::15]
    imsave("last.jpg", suspicious_frame)
    with open("name.txt", "w") as f:
        f.write(video_info["name"] + " " + video_info["date"])
    with open("url.txt", "w") as f:
        f.write(video_info["url"])

    # with open("temp.jpg", "rb") as f:
    #     frame_base64 = base64.b64encode(f.read()).decode('ascii')
    #
    #     print("encoded has length", len(frame_base64))
    # plt.imshow(frame_small)
    # plt.show()
    json = {
        "message": {
            "topic": "news",
            "data": {
                "url": video_info["url"],
                "name": video_info["name"],
                "date": video_info["date"],
                "image": "https://wiesmann.codiferes.net/share/bitmaps/test_pattern.jpg"
            }
        }
    }

    r = requests.post(url, headers=headers, json=json)
    return r.status_code, r.text


if __name__ == "__main__":
    main()
