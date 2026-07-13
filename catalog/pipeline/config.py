"""Catalog levels (undergraduate / graduate) and their source PDF + data directory.

The same pipeline runs for either level; scripts take a `level` argument (default
"undergraduate") and resolve paths through here. Data is namespaced under
catalog/data/<level>/ so the two catalogs never collide.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_ROOT = os.path.abspath(os.path.join(HERE, ".."))

LEVELS = {
    "undergraduate": {
        "pdf": "source/2024-2025 Undergraduate.pdf",
        "data": "data/undergraduate",
        "label": "Undergraduate",
        "catalogYear": "2024-2025",
    },
    "graduate": {
        "pdf": "source/2024-2025 Graduate.pdf",
        "data": "data/graduate",
        "label": "Graduate",
        "catalogYear": "2024-2025",
    },
}


def resolve(level):
    if level not in LEVELS:
        raise SystemExit(f"unknown level {level!r}; choose from {list(LEVELS)}")
    c = LEVELS[level]
    data = os.path.join(CATALOG_ROOT, c["data"])
    os.makedirs(data, exist_ok=True)
    os.makedirs(os.path.join(data, "evals"), exist_ok=True)
    return {
        "level": level,
        "label": c["label"],
        "catalogYear": c["catalogYear"],
        "pdf": os.path.join(CATALOG_ROOT, c["pdf"]),
        "data": data,
        "pages": os.path.join(data, "pages.json"),
        "ontology": os.path.join(data, "ontology.json"),
        "metrics": os.path.join(data, "metrics.json"),
        "evaluations": os.path.join(data, "evaluations.json"),
        "evals_dir": os.path.join(data, "evals"),
    }


def level_from_argv(argv, index=1, default="undergraduate"):
    return argv[index] if len(argv) > index else default
