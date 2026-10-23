"""Storage backends for the ingestion: local folder or Azure Data Lake Storage Gen2.

Both expose the same two operations, so the rest of the code does not know where data lands:

    write_bytes(container, path, data, overwrite)
    read_bytes(container, path) -> bytes | None

Bronze files are append-only and written with overwrite=False: an existing file is never
replaced. Only the station cache (state container) is overwritten.

Bronze layout, partitioned by ingestion day (Hive style):
    bronze/<dataset>/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet
"""
import io
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ingestion.config import ADLS_ACCOUNT_NAME, BRONZE_CONTAINER, DATA_ROOT, STORAGE_TARGET


class LocalStorage:
    """Containers are sub-folders of `root`. Writes are atomic (temporary file, then rename)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def describe(self, container, path):
        return str(self.root / container / path)

    def write_bytes(self, container, path, data: bytes, overwrite: bool):
        target = self.root / container / path
        if target.exists() and not overwrite:
            raise FileExistsError(f"{target} already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)

    def read_bytes(self, container, path):
        target = self.root / container / path
        return target.read_bytes() if target.exists() else None


class AdlsStorage:
    """ADLS Gen2 (hierarchical namespace). Authentication with DefaultAzureCredential:
    the Function's managed identity in Azure, the developer's `az login` locally.
    The identity needs the role "Storage Blob Data Contributor" on the storage account.
    """

    def __init__(self, account_name: str):
        from azure.identity import DefaultAzureCredential
        from azure.storage.filedatalake import DataLakeServiceClient

        self.account_name = account_name
        self.client = DataLakeServiceClient(
            account_url=f"https://{account_name}.dfs.core.windows.net",
            credential=DefaultAzureCredential(),
        )

    def describe(self, container, path):
        return f"abfss://{container}@{self.account_name}.dfs.core.windows.net/{path}"

    def write_bytes(self, container, path, data: bytes, overwrite: bool):
        file_client = self.client.get_file_system_client(container).get_file_client(path)
        if overwrite:
            file_client.upload_data(data, overwrite=True)
            return

        # upload_data(overwrite=False) does not create the file: it only appends to an existing one.
        # Create-if-missing is checked by the service (If-None-Match: *), then the content is
        # appended and committed. A file left empty by a failed upload would break every later
        # read of the dataset, so it is removed before the error is raised.
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceExistsError

        try:
            file_client.create_file(match_condition=MatchConditions.IfMissing)
        except ResourceExistsError:
            raise FileExistsError(f"{self.describe(container, path)} already exists") from None

        try:
            file_client.append_data(data, offset=0, length=len(data))
            file_client.flush_data(len(data))
        except Exception:
            try:
                file_client.delete_file()
            except Exception:
                pass                    # the original upload error is the one to report
            raise

    def read_bytes(self, container, path):
        from azure.core.exceptions import ResourceNotFoundError

        file_client = self.client.get_file_system_client(container).get_file_client(path)
        try:
            return file_client.download_file().readall()
        except ResourceNotFoundError:
            return None


def get_storage():
    """Storage backend selected by STORAGE_TARGET (local or adls)."""
    if STORAGE_TARGET == "local":
        return LocalStorage(DATA_ROOT)
    if STORAGE_TARGET == "adls":
        if not ADLS_ACCOUNT_NAME:
            raise KeyError("ADLS_ACCOUNT_NAME")
        return AdlsStorage(ADLS_ACCOUNT_NAME)
    raise ValueError(f"STORAGE_TARGET must be 'local' or 'adls', got {STORAGE_TARGET!r}")


def write_batch(storage, rows, schema: pa.Schema, dataset: str, ingestion_date: str, batch_id: str) -> str:
    """Serialize rows to Parquet and write them as one new bronze file. Returns its location."""
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), buffer)
    path = f"{dataset}/ingestion_date={ingestion_date}/batch_{batch_id}.parquet"
    storage.write_bytes(BRONZE_CONTAINER, path, buffer.getvalue(), overwrite=False)
    return storage.describe(BRONZE_CONTAINER, path)
