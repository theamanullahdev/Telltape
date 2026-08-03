import re

from .config import projects_dir


def slugify(title: str) -> str:
    slug = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "untitled"


def unique_project_slug(title: str) -> str:
    base = slugify(title)
    slug = base
    n = 2
    while (projects_dir() / slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
