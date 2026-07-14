"""CLI package — interactive menu for the v2 map-reduce pipeline.

Re-exports:
    run_menu: Main menu loop.
    STAGES:  Stage definitions for the pipeline.
"""

from aegis_phase1.v2.cli.menu import run_menu
from aegis_phase1.v2.cli.steps_config import STAGES

__all__ = [
    "run_menu",
    "STAGES",
]
