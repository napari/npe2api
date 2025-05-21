import re

def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()