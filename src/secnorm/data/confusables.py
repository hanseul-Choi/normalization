"""Bundled UTS #39 Confusables table targeting Latin and core script spoofing.

Unicode Consortium: UTS #39 Unicode Security Mechanisms.
License: Unicode License (per docs/11-dependencies.md).
"""

from __future__ import annotations

CONFUSABLES_VERSION = "16.0.0"

# Target prototype mapping for confusable lookalike characters
CONFUSABLE_MAP: dict[str, str] = {
    # Cyrillic lowercase -> Latin lowercase
    "\u0430": "a",  # Cyrillic small letter a
    "\u0441": "c",  # Cyrillic small letter es
    "\u0434": "d",  # Cyrillic small letter de
    "\u0435": "e",  # Cyrillic small letter ie
    "\u0456": "i",  # Cyrillic small letter byelorussian-ukrainian i
    "\u0458": "j",  # Cyrillic small letter je
    "\u043e": "o",  # Cyrillic small letter o
    "\u0440": "p",  # Cyrillic small letter er
    "\u0455": "s",  # Cyrillic small letter dze
    "\u0445": "x",  # Cyrillic small letter ha
    "\u0443": "y",  # Cyrillic small letter u
    "\u0501": "d",  # Cyrillic small letter komi de
    "\u051b": "q",  # Cyrillic small letter qa
    "\u051d": "w",  # Cyrillic small letter we
    # Cyrillic uppercase -> Latin uppercase
    "\u0410": "A",  # Cyrillic capital letter a
    "\u0412": "B",  # Cyrillic capital letter ve
    "\u0421": "C",  # Cyrillic capital letter es
    "\u0415": "E",  # Cyrillic capital letter ie
    "\u041d": "H",  # Cyrillic capital letter en
    "\u0406": "I",  # Cyrillic capital letter byelorussian-ukrainian i
    "\u0408": "J",  # Cyrillic capital letter je
    "\u041a": "K",  # Cyrillic capital letter ka
    "\u041c": "M",  # Cyrillic capital letter em
    "\u041e": "O",  # Cyrillic capital letter o
    "\u0420": "P",  # Cyrillic capital letter er
    "\u0405": "S",  # Cyrillic capital letter dze
    "\u0422": "T",  # Cyrillic capital letter te
    "\u0425": "X",  # Cyrillic capital letter ha
    "\u0423": "Y",  # Cyrillic capital letter u
    "\u04ae": "Y",  # Cyrillic capital letter straight u
    "\u051c": "W",  # Cyrillic capital letter we
    # Greek lowercase -> Latin lowercase
    "\u03b1": "a",  # Greek small letter alpha
    "\u03bf": "o",  # Greek small letter omicron
    "\u03bd": "v",  # Greek small letter nu
    "\u03ba": "k",  # Greek small letter kappa
    "\u03c1": "p",  # Greek small letter rho
    "\u03c4": "t",  # Greek small letter tau
    "\u03c5": "u",  # Greek small letter upsilon
    "\u03c7": "x",  # Greek small letter chi
    "\u03b9": "i",  # Greek small letter iota
    # Greek uppercase -> Latin uppercase
    "\u0391": "A",  # Greek capital letter alpha
    "\u0392": "B",  # Greek capital letter beta
    "\u0395": "E",  # Greek capital letter epsilon
    "\u0396": "Z",  # Greek capital letter zeta
    "\u0397": "H",  # Greek capital letter eta
    "\u0399": "I",  # Greek capital letter iota
    "\u039a": "K",  # Greek capital letter kappa
    "\u039c": "M",  # Greek capital letter mu
    "\u039d": "N",  # Greek capital letter nu
    "\u039f": "O",  # Greek capital letter omicron
    "\u03a1": "P",  # Greek capital letter rho
    "\u03a4": "T",  # Greek capital letter tau
    "\u03a5": "Y",  # Greek capital letter upsilon
    "\u03a7": "X",  # Greek capital letter chi
    # Latin extensions / IPA / mathematical / symbols
    "\u0251": "a",  # Latin small letter alpha
    "\u0261": "g",  # Latin small letter script g
    "\u0269": "i",  # Latin small letter iota
    "\u026a": "I",  # Latin letter small capital i
    "\u0131": "i",  # Latin small letter dotless i
    "\u0237": "j",  # Latin small letter dotless j
    "\u217c": "l",  # Small roman numeral fifty
    "\u2160": "I",  # Roman numeral one
    "\u2174": "v",  # Small roman numeral five
    "\u2179": "x",  # Small roman numeral ten
}
