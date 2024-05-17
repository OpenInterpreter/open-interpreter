import base64
import io

from PIL import Image

from ...utils.lazy_import import lazy_import

# transformers = lazy_import("transformers") # Doesn't work for some reason! We import it later.


class Vision:
    def __init__(self, computer):
        self.computer = computer
        self.model = None  # Will load upon first use
        self.tokenizer = None  # Will load upon first use

    def load(self):
        import transformers  # Wait until we use it. Transformers can't be lazy loaded for some reason!

        print(
            "Open Interpreter will use Moondream (tiny vision model) to describe images to the language model. Set `interpreter.llm.vision_renderer = None` to disable this behavior."
        )
        print(
            "Alternativley, you can use a vision-supporting LLM and set `interpreter.llm.supports_vision = True`."
        )
        model_id = "vikhyatk/moondream2"
        revision = "2024-04-02"
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            model_id, trust_remote_code=True, revision=revision
        )
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            model_id, revision=revision
        )

    def query(
        self,
        query="Describe this image.",
        base_64=None,
        path=None,
        lmc=None,
        pil_image=None,
    ):
        """
        Uses Moondream to ask query of the image (which can be a base64, path, or lmc message)
        """

        if self.model == None and self.tokenizer == None:
            self.load()

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

        enc_image = self.model.encode_image(img)
        return self.model.answer_question(enc_image, query, self.tokenizer)
