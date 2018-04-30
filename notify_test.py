import server

video_info = {
    "url": "http://doesn-t.matter",
    "name": "Freisitz",
    "date": "now",
    "image": "https://leicher.info:8000/arlo/app_images/tmp2.jpg"
}

print(server.notify_client(video_info))