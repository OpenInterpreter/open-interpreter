import difflib

from ...utils.lazy_import import lazy_import

# Lazy import of aifs, imported when needed
aifs = lazy_import('aifs')

class Files:
    def __init__(self, computer):
        self.computer = computer

    def search(self, *args, **kwargs):
        """
        Search the filesystem for the given query.
        """
        return aifs.search(*args, **kwargs)

    def edit(self, path, original_text, replacement_text):
        """
        Edits a file on the filesystem, replacing the original text with the replacement text.
        """
        with open(path, "r") as file:
            filedata = file.read()

        if original_text not in filedata:
            matches = get_close_matches_in_text(original_text, filedata)
            if matches:
                suggestions = ", ".join(matches)
                raise ValueError(
                    f"Original text not found. Did you mean one of these? {suggestions}"
                )

        filedata = filedata.replace(original_text, replacement_text)

        with open(path, "w") as file:
            file.write(filedata)


def get_close_matches_in_text(original_text, filedata, n=3):
    """
    Returns the closest matches to the original text in the content of the file.
    """
    words = filedata.split()
    original_words = original_text.split()
    len_original = len(original_words)

    matches = []
    for i in range(len(words) - len_original + 1):
        phrase = " ".join(words[i : i + len_original])
        similarity = difflib.SequenceMatcher(None, original_text, phrase).ratio()
        matches.append((similarity, phrase))

    matches.sort(reverse=True)
    return [match[1] for match in matches[:n]]
