"""Adapters between the outside world and the pure engine (Excel workbook, bundled demo data)."""

from importlib import resources

from .workbook import WorkbookError, read_book, read_workbook
from .writer import write_workbook


def demo_bytes() -> bytes:
    return resources.files("rebalancer.data").joinpath("demo.xlsx").read_bytes()


DEMO_SOURCE = "Ukázková data ze zadání (data_zadani.xlsx)"


def load_demo():
    return read_workbook(demo_bytes(), DEMO_SOURCE)


def load_demo_book():
    return read_book(demo_bytes(), DEMO_SOURCE)


__all__ = ["WorkbookError", "read_workbook", "read_book", "write_workbook", "load_demo", "load_demo_book", "demo_bytes"]
