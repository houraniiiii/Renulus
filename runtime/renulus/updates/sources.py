"""Read runtime watch metadata from the single development source register."""
import re


def read_register(path):
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| ([A-Z]\d{2}) — (.+)", line)
        if not match:
            continue
        cells = line.strip().strip("|").split("|")
        urls = re.findall(r"https://[^) ]+", cells[0])
        if not urls or match[1][0] in ("T", "R"):
            continue
        title = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", cells[0]).strip()
        entries.append({"id": match[1], "title": title, "url": urls[0],
                        "snapshot_status": cells[1].strip(), "access": cells[2].strip()})
    return entries
