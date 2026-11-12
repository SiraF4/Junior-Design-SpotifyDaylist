"""Text normalization used to match song titles and artist names across versions."""

import re

_PAREN = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_SUFFIX = re.compile(r"\s[-\u2013]\s.*(remaster|mono|stereo|deluxe|bonus|anniversary).*$", re.I)
_NONWORD = re.compile(r"[^a-z0-9\s]")


def norm_title(s):
    s = str(s).lower()
    s = _PAREN.sub(" ", s)
    s = _SUFFIX.sub("", s)
    s = _NONWORD.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_artist(s):
    first = re.split(r"[;,]|\sfeat\.?\s|\sft\.?\s", str(s).lower())[0]
    first = _NONWORD.sub(" ", first)
    return re.sub(r"\s+", " ", first).strip()