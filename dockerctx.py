""" A context manager for a docker container. """
from __future__ import division, print_function


import socket
from contextlib import contextmanager
import uuid
import logging
import time
import typing
import docker


__version__ = '2017.8.1'
__all__ = ['new_container']
logger = logging.getLogger('dockerctx')


@contextmanager
def new_container(
        image_name,
        new_container_name=lambda: uuid.uuid4().hex,
        ports=None,
        tmpfs=None,
        ready_test=None,
        privileged=None,
        docker_api_version='auto',
        **kwargs):
    """Start a docker container, and kill+remove when done.

    :param new_container_name: The container name. By default, a UUID will be used.
        If a callable, the result must be a str.
    :type new_container_name: str | callable
    :param ports: The list of port mappings to configure on the docker
        container. The format is the same as that used in the `docker`
        package, e.g. `ports={'5432/tcp': 60011}`
    :type ports: typing.Dict[str, int]
    :param tmpfs: When creating a container you can specify paths to be mounted
        with tmpfs. It can be a list or a dictionary to configure on the docker
        container. If it's a list, each item is a string specifying the path and
        (optionally) any configuration for the mount, e.g. `tmpfs={'/mnt/vol2': '',
        '/mnt/vol1': 'size=3G,uid=1000'}`
    :type tmpfs: typing.Dict[str, str]
    :param ready_test: A function to run to verify whether the container is "ready"
        (in some sense) before yielding the container back to the caller. An example
        of such a test is the `accepting_connections` function in the this module,
        which will try repeatedly to connect to a socket, until either successfuly,
        or a max timeout is reached. Use functools.partial to wrap up the args.
    :type ready_test: typing.Callable[[], bool]
    :param privileged: a privileged container is given access to all devices on
        the host as well as set some configuration in AppArmor or SELinux to allow
        the container nearly all the same access to the host as processes running
        outside containers on the host.
    :type ports: bool
    :param kwargs: These extra keyword arguments will be passed through to the
        `client.containers.run()` call.  One of the more commons ones is to pass
        a custom command through.

    """
    _ = new_container_name
    name = str(_() if callable(_) else _)
    client = docker.from_env(version=docker_api_version)

    logger.info('New postgres container: %s', name)
    container = client.containers.run(image_name, name=name, tmpfs=tmpfs, privileged=False, detach=True, ports=ports,
                                      **kwargs)
    try:
        logger.info('Waiting for postgres to be ready')
        if ready_test and not ready_test():
            raise ConnectionError(
                'Container {} not ready fast enough.'.format(name)
            )
        yield container
    finally:
        logger.info('Stopping container %s', name)
        # TODO: container.stop() does not seem to work here (e.g. for postgres)
        container.kill()
        logger.info('Removing container %s', name)
        container.remove()


def accepting_connections(host, port, timeout=20):
    """Try to make a socket connection to `(host, port)`

    I'll try every 200 ms, and eventually give up after `timeout`.

    :type host: str
    :type port: int
    :type timeout: int
    :return: True for successful connection, False otherwise
    :rtype: bool
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s = socket.create_connection((host, port))
            logger.debug('Connected!')
            s.close()
            return True
        except socket.error as ex:
            logger.debug("Connection failed with errno %s: %s",
                         ex.errno, ex.strerror)
        time.sleep(0.2)
    return False


def pg_ready(host, port, dbuser='postgres', dbname='postgres',
             timeout=20, poll_freq=0.2):
    """Wait until a postgres instance is ready to receive connections.

    .. note::

        This requires psycopg2 to be installed.

    :type host: str
    :type port: int
    :type timeout: float
    :type poll_freq: float
    """
    import psycopg2
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            conn = psycopg2.connect(
                "host={host} port={port} user={dbuser} "
                "dbname={dbname}".format(**vars())
            )
            logger.debug('Connected successfully.')
            conn.close()
            return True
        except psycopg2.OperationalError as ex:
            logger.debug("Connection failed: {0}".format(ex));
        time.sleep(poll_freq)

    logger.error('Postgres readiness check timed out.')
    return False


@contextmanager
def session_scope(session_cls):
    """Provide a transactional scope around a series of operations.

    .. note::

        This requires SQLAlchemy to be installed.

    :type: sqlalchemy.orm.Session
    """
    session = session_cls()
    try:
        logger.debug('Yielding session')
        yield session
        logger.debug('Committing session')
        session.commit()
    except:
        logger.exception('Error detected, rolling back session')
        session.rollback()
        raise
    finally:
        logger.debug('Closing session')
        session.close()


def get_open_port():
    """Return a currently-unused local network TCP port number

    This is extremely handy when running unit tests because you may
    not always be able to get the port of your choice, especially
    in a continuous-integration context.

    :return: TCP port number
    :rtype: int
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))  # Using zero means the OS assigns one
    address_info = s.getsockname()
    port = int(address_info[1])
    s.close()
    return port
