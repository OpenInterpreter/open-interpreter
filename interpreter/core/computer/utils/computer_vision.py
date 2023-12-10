import io

import cv2
import numpy as np
from PIL import Image


def find_svg_in_image(svg_code, pil_image):
    """
    Not implemented
    """
    png_image = cairosvg.svg2png(bytestring=svg_code)
    svg_image = Image.open(io.BytesIO(png_image))
    opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)

    svg_image_array = np.array(svg_image)
    if np.any(svg_image_array[:, :, 3] < 255):
        non_transparent_pixels = svg_image_array[svg_image_array[:, :, 3] > 0]
        avg_color = np.mean(non_transparent_pixels, axis=0)

        dist_black = 1 - np.linalg.norm(avg_color[:3] - [0, 0, 0])
        dist_white = 1 - np.linalg.norm(avg_color[:3] - [255, 255, 255])

        background_color = (0, 0, 0) if dist_white > dist_black else (255, 255, 255)
        background = Image.new("RGB", svg_image.size, background_color)
        background.paste(svg_image, mask=svg_image.split()[3])
        opencv_template = cv2.cvtColor(np.array(background), cv2.COLOR_RGB2GRAY)
    else:
        opencv_template = cv2.cvtColor(np.array(svg_image), cv2.COLOR_RGB2GRAY)

    template_image = opencv_template
    source_image = opencv_image

    # Open the images
    # cv2.imshow('Image', opencv_image)
    # cv2.imshow('Template', opencv_template)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # Initialize SIFT detector
    sift = cv2.SIFT_create()

    # Find the keypoints and descriptors with SIFT
    keypoints_1, descriptors_1 = sift.detectAndCompute(template_image, None)
    keypoints_2, descriptors_2 = sift.detectAndCompute(source_image, None)

    # Check if features are detected
    if descriptors_1 is None or descriptors_2 is None:
        raise ValueError(
            "Could not find enough features in one of the images. Try adjusting the SIFT parameters or using a different image."
        )

    # FLANN parameters and matcher
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    matches = flann.knnMatch(descriptors_1, descriptors_2, k=2)

    # Keep good matches: Lowe's ratio test
    good_matches = []
    for m, n in matches:
        if m and n and m.distance < 1 * n.distance:
            good_matches.append(m)

    # Draw all matches (for diagnostic purposes)
    img_matches = cv2.drawMatches(
        template_image,
        keypoints_1,
        source_image,
        keypoints_2,
        good_matches,
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )

    # Show all matches
    cv2.imshow("All Matches", img_matches)

    # Proceed only if there are enough good matches
    if len(good_matches) > 10:
        src_pts = np.float32(
            [keypoints_1[m.queryIdx].pt for m in good_matches]
        ).reshape(-1, 1, 2)
        dst_pts = np.float32(
            [keypoints_2[m.trainIdx].pt for m in good_matches]
        ).reshape(-1, 1, 2)

        # Compute Homography
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        matchesMask = mask.ravel().tolist()

        # Get the dimensions of the template image
        h, w = template_image.shape[:2]
        pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(
            -1, 1, 2
        )

        # Apply the homography to the template image's corners
        dst = cv2.perspectiveTransform(pts, M)

        # Draw bounding box in source image
        source_image = cv2.polylines(
            source_image, [np.int32(dst)], True, (0, 255, 0), 3, cv2.LINE_AA
        )
        cv2.imshow("Detected", source_image)
    else:
        print(f"Not enough good matches are found - {len(good_matches)}/10")
        matchesMask = None

    # Draw matches for visualization
    draw_params = dict(
        matchColor=(0, 255, 0), singlePointColor=None, matchesMask=matchesMask, flags=2
    )

    img_matches = cv2.drawMatches(
        template_image,
        keypoints_1,
        source_image,
        keypoints_2,
        good_matches,
        None,
        **draw_params,
    )

    # Show the matches
    cv2.imshow("Matches", img_matches)

    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # Open all images used, using the systems image viewer (not plt)
    # print(pil_image.filename)
    # print(svg_image.filename)
    # os.system('open ' + pil_image.filename)
    # os.system('open ' + svg_image.filename)
    # try:
    #     os.startfile(pil_image.filename)
    #     os.startfile(svg_image.filename)
    # except AttributeError:
    #     import subprocess
    #     subprocess.call(['open', pil_image.filename])
    #     subprocess.call(['open', svg_image.filename])


from pytesseract import Output, pytesseract


def find_text_in_image(img, text):
    # Convert PIL Image to NumPy array
    img_array = np.array(img)

    # Convert the image to grayscale
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

    # Use pytesseract to get the data from the image
    d = pytesseract.image_to_data(gray, output_type=Output.DICT)

    # Initialize an empty list to store the centers of the bounding boxes
    centers = []

    # Get the number of detected boxes
    n_boxes = len(d["level"])

    # Create a copy of the grayscale image to draw on
    img_draw = np.array(gray.copy())

    # Convert the img_draw grayscale image to RGB
    img_draw = cv2.cvtColor(img_draw, cv2.COLOR_GRAY2RGB)

    id = 0

    # Loop through each box
    for i in range(n_boxes):
        # Print the text of the box
        # If the text in the box matches the given text
        if text.lower() in d["text"][i].lower():
            # Find the start index of the matching text in the box
            start_index = d["text"][i].lower().find(text.lower())
            # Calculate the percentage of the box width that the start of the matching text represents
            start_percentage = start_index / len(d["text"][i])
            # Move the left edge of the box to the right by this percentage of the box width
            d["left"][i] = d["left"][i] + int(d["width"][i] * start_percentage)

            # Calculate the width of the matching text relative to the entire text in the box
            text_width_percentage = len(text) / len(d["text"][i])
            # Adjust the width of the box to match the width of the matching text
            d["width"][i] = int(d["width"][i] * text_width_percentage)

            # Calculate the center of the bounding box
            center = (
                d["left"][i] + d["width"][i] / 2,
                d["top"][i] + d["height"][i] / 2,
            )

            """bounding

            bounding

            bounding

            bounding

            bounding    bounding   bounding"""

            # Half both coordinates
            center = (center[0] / 2, center[1] / 2)

            # Add the center to the list
            centers.append(center)

            # Draw the bounding box on the image in red and make it slightly larger
            larger = 10
            cv2.rectangle(
                img_draw,
                (d["left"][i] - larger, d["top"][i] - larger),
                (
                    d["left"][i] + d["width"][i] + larger,
                    d["top"][i] + d["height"][i] + larger,
                ),
                (255, 0, 0),
                7,
            )

            # Create a small black square background for the ID
            cv2.rectangle(
                img_draw,
                (
                    d["left"][i] + d["width"][i] // 2 - larger * 2,
                    d["top"][i] + d["height"][i] // 2 - larger * 2,
                ),
                (
                    d["left"][i] + d["width"][i] // 2 + larger * 2,
                    d["top"][i] + d["height"][i] // 2 + larger * 2,
                ),
                (0, 0, 0),
                -1,
            )

            # Put the ID in the center of the bounding box in red
            cv2.putText(
                img_draw,
                str(id),
                (
                    d["left"][i] + d["width"][i] // 2 - larger,
                    d["top"][i] + d["height"][i] // 2 + larger,
                ),
                cv2.FONT_HERSHEY_DUPLEX,
                1,
                (255, 155, 155),
                4,
            )

            # Increment id
            id += 1

    if not centers:
        word_centers = []
        for word in text.split():
            for i in range(n_boxes):
                if word.lower() in d["text"][i].lower():
                    center = (
                        d["left"][i] + d["width"][i] / 2,
                        d["top"][i] + d["height"][i] / 2,
                    )
                    center = (center[0] / 2, center[1] / 2)
                    word_centers.append(center)

        for center1 in word_centers:
            for center2 in word_centers:
                if (
                    center1 != center2
                    and (
                        (center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2
                    )
                    ** 0.5
                    <= 400
                ):
                    centers.append(
                        ((center1[0] + center2[0]) / 2, (center1[1] + center2[1]) / 2)
                    )
                    break
            if centers:
                break

    bounding_box_image = Image.fromarray(img_draw)
    bounding_box_image.format = img.format

    # Debug by showing bounding boxes:
    # bounding_box_image.show()

    return centers, bounding_box_image
