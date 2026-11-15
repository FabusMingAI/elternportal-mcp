import copy

import pytest

from elternportal_mcp import demo
from elternportal_mcp.config import School, Settings
from elternportal_mcp.service import Service


class FakeBackend:
    def __init__(self):
        self.fetches = 0
        self.downloads = 0
        self.error = None
        self.value = demo.snapshot()
        self.pdf = b"%PDF-test"

    async def fetch(self, school):
        self.fetches += 1
        if self.error:
            raise self.error
        result = copy.deepcopy(self.value)
        result["school"] = school.school
        for child in result["children"]:
            child["school"] = school.school
            child["id"] = child["id"].replace("demo:", school.school + ":")
            for item in child["items"]:
                item["child_id"] = child["id"]
        return result

    async def download(self, *args):
        self.downloads += 1
        return self.pdf


@pytest.fixture
def live_service(tmp_path):
    backend = FakeBackend()
    service = Service(
        Settings(
            schools=[School(school="testschool")], data_dir=tmp_path, allow_pdf_downloads=True
        ),
        backend,
    )
    yield service, backend
    service.store.close()


@pytest.fixture
def demo_service(tmp_path):
    service = Service(Settings(schools=[School(school="demo")], data_dir=tmp_path))
    yield service
    service.store.close()
