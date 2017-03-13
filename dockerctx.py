""" A context manager for a docker container. """
from __future__ import division, print_function


import socket
from contextlib import contextmanager
import uuid
import logging
import time
import typing
import docker


__version__ = '2017.3.3'
__all__ = ['new_container']
logger = logging.getLogger('dockerctx')


@contextmanager
def new_container(
        image_name,
        new_container_name=lambda: uuid.uuid4().hex,
        ports=None,
        ready_test=None):
    """Start a docker container, and kill+remove when done.

    :param new_container_name: The container name. By default, a UUID will be used.
        If a callable, the result must be a str.
    :type new_container_name: str | callable
    :param ports: The list of port mappings to configure on the docker
        container. The format is the same as that used in the `docker`
        package, e.g. `ports={'5432/tcp': 60011}`
    :type ports: typing.Dict[str, int]
    :param ready_test: A function to run to verify whether the container is "ready"
        (in some sense) before yielding the container back to the caller. An example
        of such a test is the `accepting_connections` function in the this module,
        which will try repeatedly to connect to a socket, until either successfuly,
        or a max timeout is reached. Use functools.partial to wrap up the args.
    :type ready_test: typing.Callable[[], bool]

    """
    _ = new_container_name
    name = str(_() if callable(_) else _)
    client = docker.from_env()

    logger.info('New postgres container: %s', name)
    container = client.containers.run(image_name, name=name, detach=True, ports=ports)
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

