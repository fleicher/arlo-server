import json
import time
import os
import requests
from cv2 import cv2

with open("keys.json") as f:
    j = json.load(f)
    subscription_key = j["computer_vision"]
    server_url = j["static_url"]
    assert server_url[-1] != "/"


def check_images(frames):

    for n, image in enumerate(frames):

        start = time.time()
        # draw = image.copy(); cv2.cvtColor(draw, cv2.COLOR_BGR2RGB)

        print("frame #", n, end=" ", flush=True)

        imdir, imname = "../static/arlo/azure_images", "tmp{}.jpg".format(n)
        impath = os.path.join(imdir, imname)
        if not os.path.exists(imdir):
            os.makedirs(imdir)
        cv2.imwrite(impath, image)
        image_url = server_url + "/arlo/azure_images/" + imname

        vision_base_url = "https://westeurope.api.cognitive.microsoft.com/vision/v1.0/"
        vision_analyze_url = vision_base_url + "analyze"
        headers = {'Ocp-Apim-Subscription-Key': subscription_key}
        params = {'visualFeatures': 'Tags'}  # 'Categories,Description,Color'}
        data = {'url': image_url}
        response = requests.post(vision_analyze_url, headers=headers, params=params, json=data)
        print(response.content)
        response.raise_for_status()
        analysis = response.json()
        print("got:", analysis)
        print("processing time: ", time.time() - start)

        for tag in analysis["tags"]:
            if tag["name"] == "person" and tag["confidence"] > 0.6:
                return image
    return None