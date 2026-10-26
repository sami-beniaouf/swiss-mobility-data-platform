"""Stationboard client: retry policy and response validation, with a fake HTTP session."""
import pytest
import requests

from ingestion import api
from ingestion.api import FetchError, fetch_stationboard

STATION = "8504300"


def board(*station_ids):
    return {"stationboard": [{"stop": {"station": {"id": sid}}} for sid in station_ids]}


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code, self.body = status_code, body

    def json(self):
        if self.body is None:
            raise ValueError("Expecting value: line 1 column 1")
        return self.body


class FakeSession:
    """Returns (or raises) the given outcomes in order and records each request."""

    def __init__(self, *outcomes):
        self.outcomes, self.requests = list(outcomes), []

    def get(self, url, params, timeout):
        self.requests.append(params)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def waits(monkeypatch):
    """Record backoff pauses instead of sleeping."""
    recorded = []
    monkeypatch.setattr(api.time, "sleep", recorded.append)
    return recorded


def test_departures_are_returned_on_first_attempt(waits):
    session = FakeSession(FakeResponse(200, board(STATION, STATION)))

    departures, attempts = fetch_stationboard(STATION, session=session, limit=100)

    assert (len(departures), attempts) == (2, 1)
    assert session.requests == [{"id": STATION, "limit": 100}]
    assert waits == []


def test_server_errors_are_retried_with_backoff(waits):
    session = FakeSession(FakeResponse(503), FakeResponse(502), FakeResponse(200, board(STATION)))

    departures, attempts = fetch_stationboard(STATION, session=session)

    assert (len(departures), attempts) == (1, 3)
    assert waits == [2, 4]


def test_timeout_is_retried(waits):
    session = FakeSession(requests.Timeout(), FakeResponse(200, board(STATION)))

    _, attempts = fetch_stationboard(STATION, session=session)

    assert attempts == 2


@pytest.mark.parametrize("outcome", [FakeResponse(503), FakeResponse(429), requests.ConnectionError()])
def test_transient_error_fails_after_the_last_attempt(waits, outcome):
    session = FakeSession(outcome, outcome, outcome)

    with pytest.raises(FetchError, match="after 3 attempts") as error:
        fetch_stationboard(STATION, session=session, max_attempts=3)

    assert error.value.attempts == 3
    assert waits == [2, 4]                    # no pause after the last attempt


def test_permanent_error_fails_immediately(waits):
    session = FakeSession(FakeResponse(404))

    with pytest.raises(FetchError, match="HTTP 404 \\(permanent\\)") as error:
        fetch_stationboard(STATION, session=session)

    assert error.value.attempts == 1
    assert len(session.requests) == 1
    assert waits == []


def test_departures_of_another_station_are_rejected(waits):
    # Unknown ids fall back to a name search: HTTP 200 with another station's board
    session = FakeSession(FakeResponse(200, board("8507000")))

    with pytest.raises(FetchError, match="Station mismatch: asked for 8504300, got 8507000"):
        fetch_stationboard(STATION, session=session)


@pytest.mark.parametrize("body", [None, {"station": {}}], ids=["not json", "no stationboard key"])
def test_unexpected_body_is_a_failure(waits, body):
    session = FakeSession(FakeResponse(200, body))

    with pytest.raises(FetchError, match="Unexpected response body"):
        fetch_stationboard(STATION, session=session)


def test_empty_board_is_a_valid_answer(waits):
    # A small station at night can have no departure in the window: not an error
    departures, _ = fetch_stationboard(STATION, session=FakeSession(FakeResponse(200, board())))

    assert departures == []
