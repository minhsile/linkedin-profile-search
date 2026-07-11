from typing import Iterator, Protocol
from lps.models import CanonicalProfile


class SourceAdapter(Protocol):
    name: str

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        ...

    def iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]:
        ...

    def normalize(self, raw: dict) -> CanonicalProfile:
        ...
