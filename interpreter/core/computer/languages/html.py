from ..base_language import BaseLanguage


class HTML(BaseLanguage):
    file_extension = "html"
    name = "HTML"

    def __init__(self):
        super().__init__()

    def run(self, code):
        # Lmao this is so thin. But HTML should be an accepted output! It's actually terminal interface that should figure out how to render it
        yield {"html": code}
