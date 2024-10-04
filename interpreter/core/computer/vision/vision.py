import base64
import contextlib
import io
import os
import tempfile

from PIL import Image

from ...utils.lazy_import import lazy_import
from ..utils.computer_vision import pytesseract_get_text

# transformers = lazy_import("transformers") # Doesn't work for some reason! We import it later.


class Vision:
    def __init__(self, computer):
        self.computer = computer
        self.model = None  # Will load upon first use
        self.tokenizer = None  # Will load upon first use
        self.easyocr = None

    def load(self, load_moondream=True, load_easyocr=True):
        # print("Loading vision models (Moondream, EasyOCR)...\n")

        with contextlib.redirect_stdout(
            open(os.devnull, "w")
        ), contextlib.redirect_stderr(open(os.devnull, "w")):
            if self.easyocr == None and load_easyocr:
                import easyocr

                self.easyocr = easyocr.Reader(
                    ["en"]
                )  # this needs to run only once to load the model into memory

            if self.model == None and load_moondream:
                import transformers  # Wait until we use it. Transformers can't be lazy loaded for some reason!

                os.environ["TOKENIZERS_PARALLELISM"] = "false"

                if self.computer.debug:
                    print(
                        "Open Interpreter will use Moondream (tiny vision model) to describe images to the language model. Set `interpreter.llm.vision_renderer = None` to disable this behavior."
                    )
                    print(
                        "Alternatively, you can use a vision-supporting LLM and set `interpreter.llm.supports_vision = True`."
                    )
                model_id = "vikhyatk/moondream2"
                revision = "2024-04-02"
                print("loading model")

                self.model = transformers.AutoModelForCausalLM.from_pretrained(
                    model_id, trust_remote_code=True, revision=revision
                )
                self.tokenizer = transformers.AutoTokenizer.from_pretrained(
                    model_id, revision=revision
                )
                return True

    def ocr(
        self,
        base_64=None,
        path=None,
        lmc=None,
        pil_image=None,
    ):
        """
        Gets OCR of image.
        """

        if lmc:
            if "base64" in lmc["format"]:
                # # Extract the extension from the format, default to 'png' if not specified
                # if "." in lmc["format"]:
                #     extension = lmc["format"].split(".")[-1]
                # else:
                #     extension = "png"
                # Save the base64 content as a temporary file
                img_data = base64.b64decode(lmc["content"])
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".png"
                ) as temp_file:
                    temp_file.write(img_data)
                    temp_file_path = temp_file.name

                # Set path to the path of the temporary file
                path = temp_file_path

            elif lmc["format"] == "path":
                # Convert to base64
                path = lmc["content"]
        elif base_64:
            # Save the base64 content as a temporary file
            img_data = base64.b64decode(base_64)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                temp_file.write(img_data)
                temp_file_path = temp_file.name

            # Set path to the path of the temporary file
            path = temp_file_path
        elif path:
            pass
        elif pil_image:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                pil_image.save(temp_file, format="PNG")
                temp_file_path = temp_file.name

            # Set path to the path of the temporary file
            path = temp_file_path

        try:
            if not self.easyocr:
                self.load(load_moondream=False)
            result = self.easyocr.readtext(path)
            text = " ".join([item[1] for item in result])
            return text.strip()
        except ImportError:
            print(
                "\nTo use local vision, run `pip install 'open-interpreter[local]'`.\n"
            )
            return ""

    def query(
        self,
        query="Describe this image. Also tell me what text is in the image, if any.",
        base_64=None,
        path=None,
        lmc=None,
        pil_image=None,
    ):
        """
        Uses Moondream to ask query of the image (which can be a base64, path, or lmc message)
        """

        if self.model == None and self.tokenizer == None:
            try:
                success = self.load(load_easyocr=False)
            except ImportError:
                print(
                    "\nTo use local vision, run `pip install 'open-interpreter[local]'`.\n"
                )
                return ""
            if not success:
                return ""

        if lmc:
            if "base64" in lmc["format"]:
                # # Extract the extension from the format, default to 'png' if not specified
                # if "." in lmc["format"]:
                #     extension = lmc["format"].split(".")[-1]
                # else:
                #     extension = "png"

                # Decode the base64 image
                img_data = base64.b64decode(lmc["content"])
                img = Image.open(io.BytesIO(img_data))

            elif lmc["format"] == "path":
                # Convert to base64
                image_path = lmc["content"]
                img = Image.open(image_path)
        elif base_64:
            img_data = base64.b64decode(base_64)
            img = Image.open(io.BytesIO(img_data))
        elif path:
            img = Image.open(path)
        elif pil_image:
            img = pil_image

        with contextlib.redirect_stdout(open(os.devnull, "w")):
            enc_image = self.model.encode_image(img)
            answer = self.model.answer_question(
                enc_image, query, self.tokenizer, max_length=400
            )

        return answer
