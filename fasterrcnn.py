from __future__ import print_function
from __future__ import division

import keras

# import keras_retinanet
from keras_retinanet.models.resnet import custom_objects
from keras_retinanet.utils.image import read_image_bgr, preprocess_image, resize_image
from keras_retinanet.utils.visualization import draw_box, draw_caption
from keras_retinanet.utils.colors import label_color

# import miscellaneous modules
import cv2
import os
import numpy as np
import time

# set tf backend to allow memory to grow, instead of claiming everything
import tensorflow as tf


def get_session():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)


def check_images(frames, gui=False):

    # use this environment flag to change which GPU to use
    # os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    # set the modified tf session as backend in keras
    start = time.time()
    keras.backend.tensorflow_backend.set_session(get_session())

    # adjust this to point to your downloaded/trained model
    model_path = os.path.join('snapshots', 'resnet50_coco_best_v2.0.2.h5')
    if not os.path.exists(model_path):
        print("Download model from:", "https://github.com/fizyr/keras-retinanet/releases/")
        print("cwd:", os.getcwd())
    # load retinanet model
    model = keras.models.load_model(model_path, custom_objects=custom_objects)
    # print(model.summary())
    print("load up time:", time.time()-start)

    # load label to names mapping for visualization purposes
    labels_to_names = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light', 10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench', 14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow', 20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack', 25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee', 30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite', 34: 'baseball bat', 35: 'baseball glove', 36: 'skateboard', 37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange', 50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed', 60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse', 65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave', 69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book', 74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier', 79: 'toothbrush'}

    # load image
    for n, image in enumerate(frames):

        # copy to draw on
        draw = image.copy()
        draw = cv2.cvtColor(draw, cv2.COLOR_BGR2RGB)

        # preprocess image for network
        image = preprocess_image(image)
        image, scale = resize_image(image)

        # process image
        start = time.time()
        print("frame #", n, end=" ", flush=True)
        _, _, boxes, nms_classification = model.predict_on_batch(np.expand_dims(image, axis=0))
        print("processing time: ", time.time() - start)

        # compute predicted labels and scores
        predicted_labels = np.argmax(nms_classification[0, :, :], axis=1)
        scores = nms_classification[0, np.arange(nms_classification.shape[1]), predicted_labels]

        # correct for image scale
        boxes /= scale

        found_person = False
        # visualize detections
        for i in np.where(scores > 0.5)[0]:
            label = predicted_labels[i]
            if label != 0:
                continue
            found_person = True
            score = scores[i]

            color = label_color(label)

            b = boxes[0, i, :].astype(int)
            draw_box(draw, b, color=color)

            caption = "{} {:.3f}".format(labels_to_names[label], score)
            draw_caption(draw, b, caption)

        if gui:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(15, 15))
            plt.axis('off')
            plt.imshow(draw)
            plt.show()

        if found_person:
            print("found a person on frame", n)
            return draw
    return None
