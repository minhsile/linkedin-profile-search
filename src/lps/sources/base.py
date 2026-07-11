from typing import Iterator, Protocol
from lps.models import CanonicalProfile


class SourceAdapter(Protocol):
    name: str

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        """Khởi động run bất đồng bộ, trả (apify_run_id, dataset_id)."""
        ...

    def poll(self, apify_run_id: str, dataset_id: str, token: str) -> tuple[str, int]:
        """Trả (status, số item đã cào được) để theo dõi tốc độ cào."""
        ...

    def iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]:
        ...

    def normalize(self, raw: dict) -> CanonicalProfile:
        ...
