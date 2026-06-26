"""
Loads strategy memory text from a file on disk.

Public surface:
    load_strategy_memory(path) -> str
        Never raises. Returns the file's UTF-8 text content, or "" when the
        file is missing or unreadable for any reason.
"""


def load_strategy_memory(path: str) -> str:
    """Read and return the UTF-8 text content of the file at *path*.

    Returns an empty string if the file does not exist or cannot be read.
    Never raises.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""
