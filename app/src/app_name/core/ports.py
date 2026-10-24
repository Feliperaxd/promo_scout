from typing import Protocol


class Source(Protocol):
    name: str

    def find_by_global_code()