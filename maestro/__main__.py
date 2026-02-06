"""Entry point for `python -m maestro`."""

import argparse

from maestro.cli import main

parser = argparse.ArgumentParser(prog="maestro", description="Intelligent AI Tool Orchestration")
parser.add_argument("--demo", action="store_true", help="Run guided walkthrough with example tasks")
args = parser.parse_args()

main(demo=args.demo)
