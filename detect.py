from scipy import ndimage
import numpy as np
import cv2


def getSuspiciousFrames(frames, threshold=20, gui=False):
    """ detect persons on frames

    :param frames: numpy array with frames
    :param threshold: threshold when a gray scale value change is considered different
    :param gui: bool, True if plots are shown
    :return:
    """
    if gui:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        fig = plt.figure()
        gs1 = gridspec.GridSpec(2, len(frames) - 1)
        gs1.update(wspace=0.025, hspace=0.05)
        # set the spacing between axes.

    suspicous_frames = []
    for cur_frame_id in range(len(frames) - 1):
        a, b = cv2.cvtColor(frames[cur_frame_id], cv2.COLOR_BGR2GRAY), cv2.cvtColor(frames[cur_frame_id+1], cv2.COLOR_BGR2GRAY)
        frame_pixel_difference = b - a

        mean_illumination_change = np.mean(np.mean(frame_pixel_difference))
        pixels_lighter = b - a > threshold
        pixels_darker = a - b > threshold
        pixels_changed = pixels_lighter | pixels_darker

        # label each continuous area in image
        # retrieve the x and y span of the area that contains the most continuous pixels
        labelled = ndimage.label(pixels_changed)
        biggest_area_count = 0
        biggest_area_filter = None
        for l in range(1, labelled[1] + 1):
            pixels_filtered = (labelled[0] == l)
            pixels_filtered_count = np.sum(np.sum(pixels_filtered))
            if biggest_area_count < pixels_filtered_count:
                biggest_area_count = pixels_filtered_count
                biggest_area_filter = pixels_filtered
                y_indices, x_indices = np.where(pixels_filtered)
                y_span = np.max(y_indices) - np.min(y_indices)
                x_span = np.max(x_indices) - np.min(x_indices)

        ad = ""
        if abs(mean_illumination_change) < threshold and y_span > x_span and biggest_area_count > 1000:
            # only if the was no overall change in lightness and the biggest continuous area is
            # bigger than 1000 pixels and taller than wide this counts a suspicous frame
            suspicous_frames.append(cur_frame_id)
            ad = "*"

        # assert frame_pixel_difference.shape[0] % 8 == 0 and frame_pixel_difference.shape[1] % 8 == 0
        # y_dist = diff.shape[0] // 8
        # x_dist = diff.shape[1] // 8
        # c = np.empty((8, 8))
        # d = np.empty((8, 8))
        # for y in range(8):
        #     for x in range(8):
        #         d[y, x] = np.mean(np.mean(diff[y * y_dist: (y + 1) * y_dist, x * x_dist: (x + 1) * x_dist]))
        #         c[y, x] = np.mean(np.mean(pixels_changed[y * y_dist: (y + 1) * y_dist, x * x_dist: (x + 1) * x_dist]))

        if gui:
            no_rows = 4
            # real image of frame 'a'
            ax = fig.add_subplot(no_rows, len(frames) - 1, cur_frame_id + 1 + 0 * (len(frames) - 1))
            ax.title.set_text(str(round(float(mean_illumination_change))) + ad)
            plt.imshow(a, cmap="gray", vmin=0, vmax=255)

            # difference between frame a and frame b
            fig.add_subplot(no_rows, len(frames) - 1, cur_frame_id + 1 + 1 * (len(frames) - 1))
            cax = plt.imshow(b - a, cmap="hot", vmin=-100, vmax=100, interpolation='nearest')
            fig.colorbar(cax, orientation='horizontal', ticks=[-100, 0, 100])

            # binary difference between frame a and b (only if above threshold)
            fig.add_subplot(no_rows, len(frames) - 1, cur_frame_id + 1 + 2 * (len(frames) - 1))
            plt.imshow(pixels_lighter.astype(int) - pixels_darker.astype(int), cmap='hot', vmin=-1, vmax=1,
                       interpolation='nearest')

            # filter out only the biggest continuous area
            axu = fig.add_subplot(no_rows, len(frames) - 1, cur_frame_id + 1 + 3 * (len(frames) - 1))
            axu.title.set_text(str(biggest_area_count) + ": |" + str(y_span) + " _" + str(x_span))
            plt.imshow(biggest_area_filter, cmap='gray', vmin=0, vmax=1, interpolation='nearest')

            # average changes in aggregated areas (8x8 grid)
            # fig.add_subplot(no_rows, len(frames) - 1, cur_frame_id + 1 + 4 * (len(frames) - 1))
            # cax = plt.imshow(c, cmap='gray', vmin=0, vmax=1, interpolation='nearest')
            # fig.colorbar(cax, orientation='vertical', ticks=[0, 1])

    if gui:
        plt.show()
        print("showing gui")
    return suspicous_frames


def hogDetector(frames_list, overlap_threshold=0.65, gui=False):
    """
    :param frames_list:
    :param overlap_threshold: parameter for non maximum supression
    :param gui: visual output of detected image
    :return: the first detected frame (with bounding boxes inside)
    """
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # loop over the image paths
    for no, image in enumerate(frames_list):
        # load the image and resize it to (1) reduce detection time
        # and (2) improve detection accuracy
        # image = frames[frame_id, :, :].reshape(height, width)
        image = resize(image, width=min(400, image.shape[1]))

        # detect people in the image
        (rects, weights) = hog.detectMultiScale(image, winStride=(4, 4),
                                            padding=(8, 8), scale=1.05)

        # draw the original bounding boxes
        # orig = image.copy()
        # for (x, y, w, h) in rects:
        #     cv2.rectangle(orig, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # apply non-maxima suppression to the bounding boxes using a
        # fairly large overlap threshold to try to maintain overlapping
        # boxes that are still people
        rects = np.array([[x, y, x + w, y + h] for (x, y, w, h) in rects])
        # pick = imutils.object_detection.non_max_suppression(rects, probs=None, overlapThresh=0.65)
        pick = non_max_suppression_slow(rects, overlapThresh=overlap_threshold)
        if len(pick) == 0:
            continue

        # draw the final bounding boxes
        for (xA, yA, xB, yB) in pick:
            cv2.rectangle(image, (xA, yA), (xB, yB), (0, 255, 0), 2)

        if gui:
            import matplotlib.pyplot as plt

            # show some information on the number of bounding boxes
            print("[INFO] {}: {} original boxes, {} after suppression".format(
                "picture", len(rects), len(pick)))

            # show the output images
            plt.imshow(image)
            plt.show()

        return image
    return None


def non_max_suppression_slow(boxes, overlapThresh):
    # if there are no boxes, return an empty list
    if len(boxes) == 0:
        return []

    # initialize the list of picked indexes
    pick = []

    # grab the coordinates of the bounding boxes
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    # compute the area of the bounding boxes and sort the bounding
    # boxes by the bottom-right y-coordinate of the bounding box
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    # keep looping while some indexes still remain in the indexes
    # list
    while len(idxs) > 0:
        # grab the last index in the indexes list, add the index
        # value to the list of picked indexes, then initialize
        # the suppression list (i.e. indexes that will be deleted)
        # using the last index
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)
        suppress = [last]

        # loop over all indexes in the indexes list
        for pos in range(0, last):
            # grab the current index
            j = idxs[pos]

            # find the largest (x, y) coordinates for the start of
            # the bounding box and the smallest (x, y) coordinates
            # for the end of the bounding box
            xx1 = max(x1[i], x1[j])
            yy1 = max(y1[i], y1[j])
            xx2 = min(x2[i], x2[j])
            yy2 = min(y2[i], y2[j])

            # compute the width and height of the bounding box
            w = max(0, xx2 - xx1 + 1)
            h = max(0, yy2 - yy1 + 1)

            # compute the ratio of overlap between the computed
            # bounding box and the bounding box in the area list
            overlap = float(w * h) / area[j]

            # if there is sufficient overlap, suppress the
            # current bounding box
            if overlap > overlapThresh:
                suppress.append(pos)

        # delete all indexes from the index list that are in the
        # suppression list
        idxs = np.delete(idxs, suppress)

    # return only the bounding boxes that were picked
    return boxes[pick]


def resize(image, width=None, height=None, inter=cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    dim = None
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation=inter)

    # return the resized image
    return resized