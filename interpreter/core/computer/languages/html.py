from ..base_language import BaseLanguage


class HTML(BaseLanguage):
    file_extension = "html"
    name = "HTML"

    def __init__(self):
        super().__init__()

    def run(self, code):
        # Lmao this is so thin. But HTML should be an accepted output!
        yield {"html": code}
