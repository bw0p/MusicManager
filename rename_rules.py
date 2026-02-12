import re


def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def safe_filename(name: str) -> str:
    # Windows-forbidden characters + trailing dots/spaces
    name = "".join(c for c in name if c not in r'\/:*?"<>|')
    name = name.rstrip(". ").strip()
    return name


def extract_leading_index(title: str) -> int | None:
    """
    Try to parse track index from title prefix:
    "01 - Song", "1. Song", "[03] Song", "03 Song"
    """
    s = title.strip()

    patterns = [
        r"^\[(\d{1,3})\]\s+",
        r"^(\d{1,3})\s*[-.]\s+",
        r"^(\d{1,3})\s+",
    ]
    for pat in patterns:
        m = re.match(pat, s)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return None


def build_fuzzy_pattern(literal: str) -> re.Pattern:
    """
    Turn a literal removal string into a regex that is tolerant to whitespace.
    - Any run of whitespace becomes r"\s+"
    - Any "-" becomes r"\s*-\s*"
    """
    s = literal.strip()
    if not s:
        return re.compile(r"$^")  # matches nothing

    esc = re.escape(s)

    # Make escaped spaces flexible: "\ " -> "\s+"
    esc = re.sub(r"(\\\s)+", r"\\s+", esc)

    # Make hyphen separators flexible: allow optional spaces around "-"
    esc = esc.replace(r"\-", r"\s*-\s*")

    return re.compile(esc, flags=re.IGNORECASE)


def apply_remove_rules(name_no_ext: str, rules: list[str], smart_spaces: bool) -> str:
    s = name_no_ext
    for rule in rules:
        rule = rule.strip()
        if not rule:
            continue
        if smart_spaces:
            pat = build_fuzzy_pattern(rule)
            s = pat.sub("", s)
        else:
            s = s.replace(rule, "")
        s = clean_spaces(s)
    return s


def remove_between_delims(s: str, left: str, right: str) -> str:
    """
    Removes text between delimiters INCLUDING delimiters.

    - If left != right: supports nesting (e.g. [[04]] with [])
    - If left == right: treats delimiter as a toggle (e.g. &extra& with &&)
    """
    left = (left or "").strip()
    right = (right or "").strip()
    if len(left) != 1 or len(right) != 1:
        return s

    # Case 1: same delimiter on both sides (e.g. '&' ... '&')
    if left == right:
        out = []
        inside = False
        for ch in s:
            if ch == left:
                inside = not inside  # toggle
                continue
            if not inside:
                out.append(ch)
        return "".join(out)

    # Case 2: different delimiters (supports nesting)
    out = []
    depth = 0
    for ch in s:
        if ch == left:
            depth += 1
            continue
        if ch == right and depth > 0:
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)

def extract_index_with_pair(title: str, pair: str) -> int | None:
    s = title.strip()
    pair = (pair or "").strip()

    if len(pair) != 2:
        return None

    left, right = pair[0], pair[1]

    # Same-char pair: ZZ means Z03Z
    if left == right:
        m = re.match(rf"^{re.escape(left)}\s*(\d{{1,3}})\s*{re.escape(right)}\s+", s)
        if m:
            return int(m.group(1))
        return None

    # Normal: [] () {} etc
    m = re.match(rf"^{re.escape(left)}\s*(\d{{1,3}})\s*{re.escape(right)}\s+", s)
    if m:
        return int(m.group(1))
    return None
