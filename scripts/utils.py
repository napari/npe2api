import re

def normalize_name(name):
    """Normalize name as per PyPA naming conventions.

    Retrieved from
    https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization

    Parameters
    ----------
    name : str
        original distribution name

    Returns
    -------
    str
        normalized distribution name
    """
    return re.sub(r"[-_.]+", "-", name).lower()
