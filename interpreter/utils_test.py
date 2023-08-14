from utils import merge_deltas, parse_partial_json

print(parse_partial_json("""{\n  \"language\": \"shell\",\n  \"code\": \"pip
install PyPDF2 languagetools\"\n}"""))