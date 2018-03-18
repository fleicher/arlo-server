import argparse
import imaplib
import getpass
import email
import re
import os
from server import getFrames, notify_client
import detect
import time
import requests
import shutil

# pattern of links in notification mails
PATTERN = "https://arlo\.netgear\.com/hmsweb/users/library/share/link/[A-F0-9_]+"
regex = re.compile(PATTERN)


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
            driver.quit()
            return None
        print("saving video from", video_url, "at", out_path)
        driver.quit()
    req = requests.get(video_url, stream=True)
    with open(out_path, "wb") as f:
        assert req.status_code == 200
        shutil.copyfileobj(req.raw, f)
    return {"path": out_path, "url": video_url, "name": camera_name, "date": date}


if __name__ == "__main__":
    main()
