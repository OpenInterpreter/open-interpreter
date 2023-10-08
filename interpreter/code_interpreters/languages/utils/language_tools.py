from ...language_map import language_map


def get_language_file_extension(language_name):
    """
    Get the file extension for a given language
    """
    language = language_map[language_name.lower()]

    if language.file_extension:
        return language.file_extension
    else:
        return language


def get_language_proper_name(language_name):
    """
    Get the proper name for a given language
    """
    language = language_map[language_name.lower()]

    if language.proper_name:
        return language.proper_name
    else:
        return language