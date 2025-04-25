import re

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()