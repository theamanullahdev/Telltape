"""Loads config/config.yaml + .env once, cached for the process lifetime."""

from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@functools.lru_cache(maxsize=1)
def get_config() -> dict:
    load_dotenv(REPO_ROOT / ".env")
    with open(REPO_ROOT / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def require_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise RuntimeError(f"missing required env var {var_name} (check .env)")
    return value


def projects_dir() -> Path:
    return REPO_ROOT / get_config()["paths"]["projects_dir"]


def output_dir() -> Path:
    return REPO_ROOT / get_config()["paths"]["output_dir"]
