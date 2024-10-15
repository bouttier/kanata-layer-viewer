CODE_ALIASES = {
    **{f"{i}": f"Digit{i}" for i in range(10)},
    **{k: f"Key{k.upper()}" for k in "abcdefghijklmnopqrstuvwxyz"},
    "bspc": "Backspace",
    "spc": "Space",
    ";": "Semicolon",
    ",": "Comma",
    "<": "IntlBackslash",
    ".": "Period",
    "/": "Slash",
    "lalt": "AltLeft",
    "ralt": "AltRight",
}

ACTION_LABELS = {
    "XX": "",
    "lalt": "⌥",
    "ralt": "⌥",
    "lctl": "⌃",
    "rctl": "⌃",
    "lmet": "⌘",
    "rmet": "⌘",
    "lsft": "⇧",
    "tab": "↹",
    "S-tab": "⇤",
    "home": "⇱",
    "end": "⇲",
    "up": "↑",
    "down": "↓",
    "lft": "←",
    "rght": "→",
    "pgup": "⇞",
    "pgdn": "⇟",
    "bck": "⎗",
    "fwd": "⎘",
    # "mbck": "🖯",
    # "mmid": "🖯3",
    # "mlft": "🖯",
    # "mrgt": "🖯",
    # "mwu": "🖯",
    # "mwd": "🖯",
    # "mfwd": "🖯",
    "lrld": "↺",
    "ret": "⏎",
    "del": "⌦",
    "bspc": "⌫",
    "esc": "Esc",
    "C-a": "all",
    "C-z": "↶",
    "C-y": "↷",
    "C-x": "✀",
    # "C-c": "📄",
    "C-s": "💾",
    # "C-v": "📋",
    **{f"f{i}": f"F{i}" for i in range(1, 13)},
}

# should match https://github.com/jtroo/kanata/blob/main/parser/src/keys/linux.rs
KEY_SCANCODES = {
    "q": 24,
    "w": 25,
    "e": 26,
    "r": 27,
    "t": 28,
    "y": 29,
    "u": 30,
    "i": 31,
    "o": 32,
    "p": 33,
    "a": 38,
    "s": 39,
    "d": 40,
    "f": 41,
    "g": 42,
    "h": 43,
    "j": 44,
    "k": 45,
    "l": 46,
    ";": 47,
    "'": 48,
    "<": 94,
    "z": 52,
    "x": 53,
    "c": 54,
    "v": 55,
    "b": 56,
    "n": 57,
    "m": 58,
    ",": 59,
    ".": 60,
    "/": 61,
    "1": 10,
    "2": 11,
    "3": 12,
    "4": 13,
    "5": 14,
    "6": 15,
    "7": 16,
    "8": 17,
    "9": 18,
    "0": 19,
    "del": 122,
    "spc": 65,
    "bspc": 119,
    "ret": 36,
    "lalt": 64,
    "ralt": 108,
    "tab": 23,
}

KEY_SYM_LABELS = {
    16777215: "",
    65107: "◌̃",
    65134: "◌̦",
    65116: "◌̨",
    65042: "★",
    65135: "¤",
    65115: "◌̧",
    65109: "◌̆",
    65114: "◌̌",
    65110: "◌̇",
    65112: "◌̊",
    65104: "◌̀",
    65105: "◌́",
    65113: "◌̋",
    65108: "◌̄",
    65513: "⌥",
    65511: "⌘",
}

KEY_STRING_LABELS = {
    " ": "espace",
    " ": "espace insécable fine",
}
