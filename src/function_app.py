"""Azure Function: runs the ingestion every 15 minutes.

Deployment root is src/: this file, host.json, requirements.txt and the ingestion package.
Configuration comes from the Function's app settings (same variable names as .env);
Oracle secrets are Key Vault references resolved by the platform with the managed identity.
"""
import base64
import logging
import os
import tempfile
from pathlib import Path

import azure.functions as func

from ingestion.run import main

app = func.FunctionApp()


def _prepare_wallet():
    """Rebuild the Oracle wallet file from ORACLE_WALLET_PEM_B64 into a temporary folder.

    Only ewallet.pem is needed in thin mode; the DSN is a full connect descriptor,
    so tnsnames.ora is not required. The private key stays encrypted with the wallet password.
    """
    encoded = os.environ.get("ORACLE_WALLET_PEM_B64")
    if not encoded:
        return
    wallet_dir = Path(tempfile.gettempdir()) / "oracle_wallet"
    wallet_dir.mkdir(mode=0o700, exist_ok=True)
    pem_path = wallet_dir / "ewallet.pem"
    pem_path.write_bytes(base64.b64decode(encoded))
    pem_path.chmod(0o600)
    os.environ["ORACLE_WALLET_DIR"] = str(wallet_dir)


# NCRONTAB with seconds, evaluated in UTC: second 0 of minutes 0, 15, 30 and 45.
@app.timer_trigger(arg_name="timer", schedule="0 */15 * * * *", run_on_startup=False, use_monitor=True)
def ingest_stationboard(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer is past due: the previous schedule was missed")

    _prepare_wallet()
    exit_code = main()

    # A non-zero code must fail the invocation, so that it is counted as a failure and can raise an alert.
    if exit_code != 0:
        raise RuntimeError(f"Ingestion run failed with exit code {exit_code}, see the run log above")
