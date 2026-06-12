import os
from datetime import datetime, timezone
from pathlib import Path

from titlecase import titlecase

DOCS_DIR = str(Path(__file__).resolve().parent)


def ensure_accessed_frontmatter(filepath: str) -> None:
    with open(filepath, "r") as f:
        content = f.read()

    if content.startswith("---"):
        return

    mtime = os.path.getmtime(filepath)
    date_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    frontmatter = f"---\naccessed: {date_str}\n---\n\n"
    with open(filepath, "w") as f:
        f.write(frontmatter + content)


special_transform = {"llms.md": "llms.txt"}
md_list = list(set(os.listdir(DOCS_DIR)) - set(special_transform))
md_list = list(special_transform.keys()) + sorted(md_list)
for fn in md_list:
    if fn.endswith(".md") and "README" not in fn:
        ensure_accessed_frontmatter(os.path.join(DOCS_DIR, fn))
        header = special_transform.get(fn, titlecase(" ".join(fn.split(".md")[0].split("-"))))
        print(f"- [{header}]({fn})")
