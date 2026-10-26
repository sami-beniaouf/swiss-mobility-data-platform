"""Storage backends: bronze files are append-only, failed uploads leave nothing behind."""
import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from ingestion import storage as storage_module
from ingestion.storage import AdlsStorage, LocalStorage, get_storage, write_batch

PARQUET = b"PAR1...PAR1"


# --- local folder -----------------------------------------------------------------------

def test_local_bronze_file_is_never_overwritten(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.write_bytes("bronze", "ds/batch_1.parquet", PARQUET, overwrite=False)

    with pytest.raises(FileExistsError):
        storage.write_bytes("bronze", "ds/batch_1.parquet", b"other", overwrite=False)

    assert storage.read_bytes("bronze", "ds/batch_1.parquet") == PARQUET


def test_local_cache_can_be_overwritten(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.write_bytes("state", "cache.json", b"old", overwrite=True)
    storage.write_bytes("state", "cache.json", b"new", overwrite=True)

    assert storage.read_bytes("state", "cache.json") == b"new"


def test_local_write_leaves_no_temporary_file(tmp_path):
    LocalStorage(tmp_path).write_bytes("bronze", "ds/batch_1.parquet", PARQUET, overwrite=False)

    assert [p.name for p in (tmp_path / "bronze" / "ds").iterdir()] == ["batch_1.parquet"]


def test_local_missing_file_reads_as_none(tmp_path):
    assert LocalStorage(tmp_path).read_bytes("state", "missing.json") is None


# --- ADLS, with a fake Data Lake client ---------------------------------------------------

class FakeFileClient:
    """Records the calls made by AdlsStorage, like the Data Lake SDK file client."""

    def __init__(self, exists=False, fail_on=None):
        self.exists, self.fail_on, self.calls, self.content = exists, fail_on, [], None

    def _call(self, name):
        self.calls.append(name)
        if name == self.fail_on:
            raise ConnectionError("network cut")

    def create_file(self, match_condition=None):
        self._call("create")
        if self.exists:
            raise ResourceExistsError("The specified path already exists.")

    def append_data(self, data, offset, length):
        self._call("append")
        self.content = data

    def flush_data(self, length):
        self._call("flush")

    def delete_file(self):
        self._call("delete")

    def upload_data(self, data, overwrite):
        self._call(f"upload(overwrite={overwrite})")
        self.content = data

    def download_file(self):
        if not self.exists:
            raise ResourceNotFoundError("The specified path does not exist.")
        return io.BytesIO(b"cached")


def adls_with(file_client):
    """AdlsStorage wired to a fake client, without credentials or network."""
    storage = AdlsStorage.__new__(AdlsStorage)
    storage.account_name = "stswissmobility"

    class FakeServiceClient:
        def get_file_system_client(self, container):
            return self

        def get_file_client(self, path):
            return file_client

    storage.client = FakeServiceClient()
    return storage


def test_adls_new_bronze_file_is_created_then_written():
    client = FakeFileClient()

    adls_with(client).write_bytes("bronze", "ds/batch_1.parquet", PARQUET, overwrite=False)

    assert client.calls == ["create", "append", "flush"]
    assert client.content == PARQUET


def test_adls_existing_bronze_file_is_never_overwritten():
    client = FakeFileClient(exists=True)

    with pytest.raises(FileExistsError, match="abfss://bronze@stswissmobility"):
        adls_with(client).write_bytes("bronze", "ds/batch_1.parquet", PARQUET, overwrite=False)

    assert client.calls == ["create"]          # nothing was appended to the existing file


@pytest.mark.parametrize("failing_step", ["append", "flush"])
def test_adls_interrupted_upload_removes_the_incomplete_file(failing_step):
    client = FakeFileClient(fail_on=failing_step)

    with pytest.raises(ConnectionError):
        adls_with(client).write_bytes("bronze", "ds/batch_1.parquet", PARQUET, overwrite=False)

    assert client.calls[-1] == "delete"


def test_adls_cache_is_uploaded_with_overwrite():
    client = FakeFileClient()

    adls_with(client).write_bytes("state", "cache.json", b"{}", overwrite=True)

    assert client.calls == ["upload(overwrite=True)"]


def test_adls_missing_file_reads_as_none():
    assert adls_with(FakeFileClient()).read_bytes("state", "cache.json") is None


# --- backend selection and file layout -----------------------------------------------------

def test_adls_without_account_name_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(storage_module, "STORAGE_TARGET", "adls")
    monkeypatch.setattr(storage_module, "ADLS_ACCOUNT_NAME", None)

    with pytest.raises(KeyError, match="ADLS_ACCOUNT_NAME"):
        get_storage()


def test_unknown_storage_target_is_rejected(monkeypatch):
    monkeypatch.setattr(storage_module, "STORAGE_TARGET", "s3")

    with pytest.raises(ValueError, match="must be 'local' or 'adls'"):
        get_storage()


def test_batch_is_written_to_its_ingestion_day_partition(tmp_path):
    storage = LocalStorage(tmp_path)
    schema = pa.schema([("value", pa.int32())])

    location = write_batch(storage, [{"value": 1}], schema, "ds", "2026-10-26", "20261026T090000Z")

    expected = tmp_path / "bronze" / "ds" / "ingestion_date=2026-10-26" / "batch_20261026T090000Z.parquet"
    assert location == str(expected)
    assert pq.read_table(expected).to_pylist() == [{"value": 1}]
