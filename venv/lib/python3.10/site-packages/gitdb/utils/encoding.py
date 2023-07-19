def force_bytes(data, encoding="utf-8"):
    if isinstance(data, bytes):
        return data

    if isinstance(data, str):
        return data.encode(encoding)

    return data


def force_text(data, encoding="utf-8"):
    if isinstance(data, str):
        return data

    if isinstance(data, bytes):
        return data.decode(encoding)

    return str(data, encoding)
