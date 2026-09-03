"""Realign the 36 UI keys that were inserted in the wrong locale order."""
import json
import re
import sys

sys.path.insert(0, "/tmp")
from add_keys import KEYS, T  # noqa: E402  (same table, correct values per locale)

PATH = "/app/frontend/src/i18n/checkoutStrings.js"
src = open(PATH, encoding="utf-8").read()
fixed = 0

for loc, vals in T.items():
    want = dict(zip(KEYS, vals))
    head, rest = src.split(f"\n  {loc}: {{", 1)
    body, tail = rest.split("\n  },", 1)
    new_lines = []
    for line in body.split("\n"):
        m = re.match(r"^(\s*)(\w+): ", line)
        if m and m.group(2) in want:
            new_lines.append(f'{m.group(1)}{m.group(2)}: {json.dumps(want[m.group(2)], ensure_ascii=False)},')
            fixed += 1
        else:
            new_lines.append(line)
    src = head + f"\n  {loc}: {{" + "\n".join(new_lines) + "\n  }," + tail

open(PATH, "w", encoding="utf-8").write(src)
print("realigned lines:", fixed)
