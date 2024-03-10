import hashlib
import io
import os
import subprocess
from typing import List

import cv2
import nltk
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from sentence_transformers import SentenceTransformer, util

from .....terminal_interface.utils.oi_dir import oi_dir
from ...utils.computer_vision import pytesseract_get_text_bounding_boxes

try:
    nltk.corpus.words.words()
except LookupError:
    nltk.download("words", quiet=True)
from nltk.corpus import words

# Create a set of English words
english_words = set(words.words())


def take_screenshot_to_pil(filename="temp_screenshot.png"):
    # Capture the screenshot and save it to a temporary file
    subprocess.run(["screencapture", "-x", filename], check=True)

    # Open the image file with PIL
    with open(filename, "rb") as f:
        image_data = f.read()
    image = Image.open(io.BytesIO(image_data))

    # Optionally, delete the temporary file if you don't need it after loading
    os.remove(filename)

    return image


from ...utils.computer_vision import find_text_in_image


def point(description, screenshot=None, debug=False, hashes=None):
    if description.startswith('"') and description.endswith('"'):
        return find_text_in_image(description.strip('"'), screenshot)
    else:
        return find_icon(description, screenshot, debug, hashes)


def find_icon(description, screenshot=None, debug=False, hashes=None):
    if screenshot == None:
        image_data = take_screenshot_to_pil()
    else:
        image_data = screenshot

    if hashes == None:
        hashes = {}

    image_width, image_height = image_data.size

    # Create a temporary file to save the image data
    #   with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
    #     temp_file.write(base64.b64decode(request.base64))
    #     temp_image_path = temp_file.name
    #   print("yeah took", time.time()-thetime)

    icons_bounding_boxes = get_element_boxes(image_data, debug)

    # Filter out extremes
    icons_bounding_boxes = [
        box
        for box in icons_bounding_boxes
        if 10 <= box["width"] <= 500 and 10 <= box["height"] <= 500
    ]

    # Compute center_x and center_y for each box
    for box in icons_bounding_boxes:
        box["center_x"] = box["x"] + box["width"] / 2
        box["center_y"] = box["y"] + box["height"] / 2

    # # Filter out text

    response = pytesseract_get_text_bounding_boxes(screenshot)

    if debug:
        # Create a draw object
        image_data_copy = image_data.copy()
        draw = ImageDraw.Draw(image_data_copy)
        # Draw red rectangles around all blocks
        for block in response:
            left, top, width, height = (
                block["left"],
                block["top"],
                block["width"],
                block["height"],
            )
            draw.rectangle([(left, top), (left + width, top + height)], outline="blue")
        # Save the image to the desktop
        debug_path = os.path.join(os.path.expanduser("~"), "Desktop", "oi-debug")
        if not os.path.exists(debug_path):
            os.makedirs(debug_path)
        image_data_copy.save(os.path.join(debug_path, "pytesseract_blocks_image.png"))

    blocks = [
        b for b in response if len(b["text"]) > 2
    ]  # icons are sometimes text, like "X"

    # Filter blocks so the text.lower() needs to be a real word in the English dictionary
    filtered_blocks = []
    for b in blocks:
        words = b["text"].lower().split()
        words = [
            "".join(e for e in word if e.isalnum()) for word in words
        ]  # remove punctuation
        if all(word in english_words for word in words):
            filtered_blocks.append(b)
    blocks = filtered_blocks

    if debug:
        # Create a draw object
        image_data_copy = image_data.copy()
        draw = ImageDraw.Draw(image_data_copy)
        # Draw red rectangles around all blocks
        for block in blocks:
            left, top, width, height = (
                block["left"],
                block["top"],
                block["width"],
                block["height"],
            )
            draw.rectangle([(left, top), (left + width, top + height)], outline="green")
        image_data_copy.save(
            os.path.join(debug_path, "pytesseract_filtered_blocks_image.png")
        )

    if debug:
        # Create a draw object
        image_data_copy = image_data.copy()
        draw = ImageDraw.Draw(image_data_copy)
        # Draw red rectangles around all blocks
        for block in blocks:
            left, top, width, height = (
                block["left"],
                block["top"],
                block["width"],
                block["height"],
            )
            draw.rectangle([(left, top), (left + width, top + height)], outline="green")
            # Draw the detected text in the rectangle in small font
            # Use PIL's built-in bitmap font
            font = ImageFont.load_default()
            draw.text(
                (block["left"], block["top"]), block["text"], fill="red", font=font
            )
        image_data_copy.save(
            os.path.join(debug_path, "pytesseract_filtered_blocks_image_with_text.png")
        )

    # Create an empty list to store the filtered boxes
    filtered_boxes = []

    # Filter out boxes that fall inside text
    for box in icons_bounding_boxes:
        if not any(
            text_box["left"] <= box["x"] <= text_box["left"] + text_box["width"]
            and text_box["top"] <= box["y"] <= text_box["top"] + text_box["height"]
            and text_box["left"]
            <= box["x"] + box["width"]
            <= text_box["left"] + text_box["width"]
            and text_box["top"]
            <= box["y"] + box["height"]
            <= text_box["top"] + text_box["height"]
            for text_box in blocks
        ):
            filtered_boxes.append(box)
        else:
            pass
            # print("Filtered out an icon because I think it is text.")

    icons_bounding_boxes = filtered_boxes

    # Filter out boxes that intersect with text at all
    filtered_boxes = []
    for box in icons_bounding_boxes:
        if not any(
            max(text_box["left"], box["x"])
            < min(text_box["left"] + text_box["width"], box["x"] + box["width"])
            and max(text_box["top"], box["y"])
            < min(text_box["top"] + text_box["height"], box["y"] + box["height"])
            for text_box in blocks
        ):
            filtered_boxes.append(box)
    icons_bounding_boxes = filtered_boxes

    # # (DISABLED)
    # # Filter to the most icon-like dimensions

    # # Desired dimensions
    # desired_width = 30
    # desired_height = 30

    # # Calculating the distance of each box's dimensions from the desired dimensions
    # for box in icons_bounding_boxes:
    #     width_diff = abs(box["width"] - desired_width)
    #     height_diff = abs(box["height"] - desired_height)
    #     # Sum of absolute differences as a simple measure of "closeness"
    #     box["distance"] = width_diff + height_diff

    # # Sorting the boxes based on their closeness to the desired dimensions
    # sorted_boxes = sorted(icons_bounding_boxes, key=lambda x: x["distance"])

    # # Selecting the top 150 closest boxes
    # icons_bounding_boxes = sorted_boxes  # DISABLED [:150]

    # Expand a little

    # Define the pixel expansion amount
    pixel_expand = int(os.getenv("OI_POINT_PIXEL_EXPAND", 7))

    # Expand each box by pixel_expand
    for box in icons_bounding_boxes:
        # Expand x, y by pixel_expand if they are greater than 0
        box["x"] = box["x"] - pixel_expand if box["x"] - pixel_expand >= 0 else box["x"]
        box["y"] = box["y"] - pixel_expand if box["y"] - pixel_expand >= 0 else box["y"]

        # Expand w, h by pixel_expand, but not beyond image_width and image_height
        box["width"] = (
            box["width"] + pixel_expand * 2
            if box["x"] + box["width"] + pixel_expand * 2 <= image_width
            else image_width - box["x"] - box["width"]
        )
        box["height"] = (
            box["height"] + pixel_expand * 2
            if box["y"] + box["height"] + pixel_expand * 2 <= image_height
            else image_height - box["y"] - box["height"]
        )

    # Combine overlapping icons
    if os.getenv("OI_POINT_OVERLAP", "True") == "True":
        combined_boxes = []
        for box in icons_bounding_boxes:
            # Check if the box overlaps with any box in the combined_boxes list
            for i, combined_box in enumerate(combined_boxes):
                if (
                    box["x"] < combined_box["x"] + combined_box["width"]
                    and box["x"] + box["width"] > combined_box["x"]
                    and box["y"] < combined_box["y"] + combined_box["height"]
                    and box["y"] + box["height"] > combined_box["y"]
                ):
                    # The boxes overlap, combine them
                    combined_box["x"] = min(box["x"], combined_box["x"])
                    combined_box["y"] = min(box["y"], combined_box["y"])
                    combined_box["width"] = (
                        max(
                            box["x"] + box["width"],
                            combined_box["x"] + combined_box["width"],
                        )
                        - combined_box["x"]
                    )
                    combined_box["height"] = (
                        max(
                            box["y"] + box["height"],
                            combined_box["y"] + combined_box["height"],
                        )
                        - combined_box["y"]
                    )
                    break
            else:
                # The box does not overlap with any box in the combined_boxes list, add it to the list
                combined_boxes.append(box.copy())
        icons_bounding_boxes = combined_boxes

    icons = []
    for box in icons_bounding_boxes:
        x, y, w, h = box["x"], box["y"], box["width"], box["height"]

        icon_image = image_data.crop((x, y, x + w, y + h))

        # icon_image.show()
        # input("Press Enter to finish looking at the image...")

        icon = {}
        icon["data"] = icon_image
        icon["x"] = x
        icon["y"] = y
        icon["width"] = w
        icon["height"] = h

        icon_image_hash = hashlib.sha256(icon_image.tobytes()).hexdigest()
        icon["hash"] = icon_image_hash

        # Calculate the relative central xy coordinates of the bounding box
        center_x = box["center_x"] / image_width  # Relative X coordinate
        center_y = box["center_y"] / image_height  # Relative Y coordinate
        icon["coordinate"] = (center_x, center_y)

        icons.append(icon)

    # Draw and show an image with the full screenshot and all the icons bounding boxes drawn on it in red
    if debug:
        image_data_copy = image_data.copy()
        draw = ImageDraw.Draw(image_data_copy)
        for icon in icons:
            x, y, w, h = icon["x"], icon["y"], icon["width"], icon["height"]
            draw.rectangle([(x, y), (x + w, y + h)], outline="red")
        desktop = os.path.join(os.path.join(os.path.expanduser("~")), "Desktop")
        image_data_copy.save(os.path.join(desktop, "point_vision.png"))

    top_icons = image_search(description, icons, hashes)

    coordinates = [t["coordinate"] for t in top_icons]

    # Return the top pick icon data
    return coordinates


# torch.set_num_threads(4)

fast_model = True

# First, we load the respective CLIP model
model = SentenceTransformer("clip-ViT-B-32")


import os

import timm

if fast_model == False:
    # Check if the model file exists
    if not os.path.isfile(model_path):
        # If not, create and save the model
        model = timm.create_model(
            "vit_base_patch16_siglip_224",
            pretrained=True,
            num_classes=0,
        )
        model = model.eval()
        torch.save(model.state_dict(), model_path)
    else:
        # If the model file exists, load the model from the saved state
        model = timm.create_model(
            "vit_base_patch16_siglip_256",
            pretrained=False,  # Don't load pretrained weights
            num_classes=0,
        )
        model.load_state_dict(torch.load(model_path))
        model = model.eval()

    # get model specific transforms (normalization, resize)
    data_config = timm.data.resolve_model_data_config(model)
    transforms = timm.data.create_transform(**data_config, is_training=False)

    def embed_images(images: List[Image.Image], model, transforms):
        # Stack images along the batch dimension
        image_batch = torch.stack([transforms(image) for image in images])
        # Get embeddings
        embeddings = model(image_batch)
        return embeddings

    # Usage:
    # images = [Image.open(io.BytesIO(image_bytes1)), Image.open(io.BytesIO(image_bytes2)), ...]
    # embeddings = embed_images(images, model, transforms)


device = torch.device("cpu")  # or 'cpu' for CPU, 'cuda:0' for the first GPU, etc.
# Move the model to the specified device
model = model.to(device)


def image_search(query, icons, hashes):
    hashed_icons = [icon for icon in icons if icon["hash"] in hashes]
    unhashed_icons = [icon for icon in icons if icon["hash"] not in hashes]

    # Embed the unhashed icons
    if fast_model:
        query_and_unhashed_icons_embeds = model.encode(
            [query] + [icon["data"] for icon in unhashed_icons],
            batch_size=128,
            convert_to_tensor=True,
            show_progress_bar=False,
        )
    else:
        query_and_unhashed_icons_embeds = embed_images(
            [query] + [icon["data"] for icon in unhashed_icons], model, transforms
        )

    query_embed = query_and_unhashed_icons_embeds[0]
    unhashed_icons_embeds = query_and_unhashed_icons_embeds[1:]

    # Store hashes for unhashed icons
    for icon, emb in zip(unhashed_icons, unhashed_icons_embeds):
        hashes[icon["hash"]] = emb

    # Move tensors to the specified device before concatenating
    unhashed_icons_embeds = unhashed_icons_embeds.to(device)

    # Include hashed icons in img_emb
    img_emb = torch.cat(
        [unhashed_icons_embeds]
        + [hashes[icon["hash"]].unsqueeze(0) for icon in hashed_icons]
    )

    # Perform semantic search
    hits = util.semantic_search(query_embed, img_emb)[0]

    # Filter hits with score over 90
    results = [hit for hit in hits if hit["score"] > 90]

    # Ensure top result is included
    if hits and (hits[0] not in results):
        results.insert(0, hits[0])

    # Convert results to original icon format
    return [icons[hit["corpus_id"]] for hit in results]


def get_element_boxes(image_data, debug):
    if debug:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        debug_path = os.path.join(desktop_path, "oi-debug")
        if not os.path.exists(debug_path):
            os.makedirs(debug_path)

    # Re-import the original image for contrast adjustment
    # original_image = cv2.imread(image_path)

    # Convert the image to a format that PIL can work with
    # pil_image = Image.fromarray(cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB))

    pil_image = image_data

    # Apply an extreme contrast filter
    enhancer = ImageEnhance.Contrast(pil_image)
    contrasted_image = enhancer.enhance(20.0)  # Significantly increase contrast

    if debug:
        contrasted_image_path = os.path.join(debug_path, "contrasted_image.jpg")
        contrasted_image.save(contrasted_image_path)
        print(f"DEBUG: Contrasted image saved to {contrasted_image_path}")

    # Convert the contrast-enhanced image to OpenCV format
    contrasted_image_cv = cv2.cvtColor(np.array(contrasted_image), cv2.COLOR_RGB2BGR)

    # Convert the contrast-enhanced image to grayscale
    gray_contrasted = cv2.cvtColor(contrasted_image_cv, cv2.COLOR_BGR2GRAY)
    if debug:
        image_path = os.path.join(debug_path, "gray_contrasted_image.jpg")
        cv2.imwrite(image_path, gray_contrasted)
        print("DEBUG: Grayscale contrasted image saved at:", image_path)

    # Apply adaptive thresholding to create a binary image where the GUI elements are isolated
    binary_contrasted = cv2.adaptiveThreshold(
        gray_contrasted,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2,
    )

    if debug:
        binary_contrasted_image_path = os.path.join(
            debug_path, "binary_contrasted_image.jpg"
        )
        cv2.imwrite(binary_contrasted_image_path, binary_contrasted)
        print(f"DEBUG: Binary contrasted image saved to {binary_contrasted_image_path}")

    # Find contours from the binary image
    contours_contrasted, _ = cv2.findContours(
        binary_contrasted, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
    )

    # Optionally, draw contours on the image for visualization
    contour_image = np.zeros_like(binary_contrasted)
    cv2.drawContours(contour_image, contours_contrasted, -1, (255, 255, 255), 1)

    if debug:
        contoured_contrasted_image_path = os.path.join(
            debug_path, "contoured_contrasted_image.jpg"
        )
        cv2.imwrite(contoured_contrasted_image_path, contour_image)
        print(
            f"DEBUG: Contoured contrasted image saved at: {contoured_contrasted_image_path}"
        )

    # Initialize an empty list to store the boxes
    boxes = []
    for contour in contours_contrasted:
        # Get the rectangle that bounds the contour
        x, y, w, h = cv2.boundingRect(contour)
        # Append the box as a dictionary to the list
        boxes.append({"x": x, "y": y, "width": w, "height": h})

    return boxes
