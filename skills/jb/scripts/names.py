import re

YEAR = re.compile(r" \(\d{4}\)$")
FORBIDDEN = set(':?*"<>|')


def flaws(name):
    found_items = []
    if name != name.strip():
        found_items.append("leading or trailing space")
    if "  " in name:
        found_items.append("double space")
    if name.rstrip().endswith("."):
        found_items.append("trailing dot")
    if YEAR.search(name):
        found_items.append("year in the name")
    if FORBIDDEN & set(name):
        found_items.append("forbidden character")
    return found_items


def check(report, path, name):
    for default in flaws(name):
        report.add(path, "name", default)


def sanitize(name):
    name = re.sub(r"\s*:\s*", " - ", name)
    name = re.sub(r"\s*[/\\]\s*", " - ", name)
    name = "".join(c for c in name if c not in '?*"<>|')
    return re.sub(r"\s+", " ", name).strip().rstrip(". ").strip()
