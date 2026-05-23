"""Unit-ish tests for the helpers in dockerctx that don't need a full container,
plus a couple of Docker-backed tests that cover branches the existing
integration tests miss (ready_test failure, persist=True, errors-during-cleanup).
"""
import socket
import threading
import time

import docker
import pytest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

from dockerctx import (
    accepting_connections,
    get_open_port,
    new_container,
    pg_ready,
    session_scope,
)


def test_get_open_port_returns_usable_port():
    port = get_open_port()
    assert isinstance(port, int)
    assert 0 < port < 65536
    # The reported port must be free immediately after the call.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('', port))
    finally:
        s.close()


def _serve_once(port, ready):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(1)
    ready.set()
    try:
        conn, _ = server.accept()
        conn.close()
    finally:
        server.close()


def test_accepting_connections_success():
    port = get_open_port()
    ready = threading.Event()
    t = threading.Thread(target=_serve_once, args=(port, ready), daemon=True)
    t.start()
    assert ready.wait(timeout=5)
    assert accepting_connections('127.0.0.1', port, timeout=5) is True
    t.join(timeout=5)


def test_accepting_connections_timeout():
    # Nothing is listening on this port — we want the polling loop to give up.
    port = get_open_port()
    t0 = time.time()
    assert accepting_connections('127.0.0.1', port, timeout=1) is False
    # Sanity: it really waited (rather than e.g. raising immediately).
    assert time.time() - t0 >= 1


def test_pg_ready_timeout():
    # No postgres is listening; pg_ready should poll until timeout and return False.
    port = get_open_port()
    t0 = time.time()
    assert pg_ready('127.0.0.1', port, timeout=1, poll_freq=0.1) is False
    assert time.time() - t0 >= 1


def _make_sqlite_session():
    engine = sqlalchemy.create_engine('sqlite:///:memory:')
    return sessionmaker(bind=engine)


def test_session_scope_commits_on_success():
    Session = _make_sqlite_session()
    with session_scope(Session) as session:
        # Run a trivial query so something happens in the transaction.
        result = session.execute(sqlalchemy.text('SELECT 1')).scalar()
        assert result == 1


def test_session_scope_rolls_back_on_exception():
    Session = _make_sqlite_session()

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with session_scope(Session) as session:
            session.execute(sqlalchemy.text('SELECT 1'))
            raise Boom('synthetic failure')


# --- Docker-backed tests covering branches missed by the existing suite ---

def test_ready_test_failure_raises_connection_error():
    """If ready_test returns False, new_container must raise ConnectionError
    and still tear the container down on the way out."""
    with pytest.raises(ConnectionError):
        with new_container(
                image_name='alpine:latest',
                command='sleep 30',
                ready_test=lambda: False,
                docker_api_version='1.24'):
            pytest.fail('Should not reach the body when ready_test fails')


def test_persist_keeps_container_running():
    """persist=lambda: True must skip stop+remove. We clean up by hand."""
    client = docker.from_env(version='1.24')
    container_id = None
    try:
        with new_container(
                image_name='alpine:latest',
                command='sleep 30',
                persist=lambda: True,
                docker_api_version='1.24') as container:
            container_id = container.id

        # If persist worked, the container should still exist after exit.
        still_there = client.containers.get(container_id)
        assert still_there.id == container_id
    finally:
        if container_id is not None:
            try:
                c = client.containers.get(container_id)
                c.remove(force=True)
            except docker.errors.NotFound:
                pass


def test_cleanup_errors_are_logged_not_raised():
    """If the container is gone before the context exits, both stop() and
    remove() raise docker.errors.APIError; new_container must swallow them."""
    with new_container(
            image_name='alpine:latest',
            command='sleep 30',
            docker_api_version='1.24') as container:
        # Yank the container out from under the context manager.
        container.remove(force=True)
    # Reaching this line means the APIError branches were exercised and swallowed.
