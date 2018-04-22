# arlo-server
Server for detecting persons on arlo Security cams and sending push notifications 

For setup of Firebase messages: 

* download a JSON with the private service account key description from Firebase Console 
-> 3 dots next to relevant project and click on settings -> tab service accounts -> generate new private key

* activate messaging API for this project

Register on Microsoft Azure to use their Computer Vision API. Get an api key and include it in keys.json (see below)

Create keys.json in git repository with your keys:

```json
{
  "computer_vision": "xxxxxxxxxxxxxxxxxxxxxx",  # Azure Computer Vision API key
  "static_url": "http://server-url.com:port/path/to/static", # this servers address where this script is running
  "arlo_user": "XXXXXXXXX@XXXXXXXXXX.com",  
  "arlo_password": "XXXXXXXXX",
  "firebase_project_id": "quickstart-android-XXXX"
}
```
