
.. image:: https://travis-ci.org/cjrh/dockerctx.svg?branch=master
    :target: https://travis-ci.org/cjrh/dockerctx

dockerctx
=========

`dockerctx` is a context manager for managing the lifetime of a docker container.

The main use case is for setting up scaffolding for running tests, where you want
something a little broader than *unit tests*, but less heavily integrated than,
say, what you might write using `Robot framework`_.

.. _Robot framework: http://robotframework.org/

Install
-------

.. code-block:: bash

    $ pip install dockerctx

For dev, you have to use flit_:

.. code-block:: bash

    $ pip install flit
    $ flit install

The development-specific requirements will be installed automatically.

.. _flit: https://flit.readthedocs.io/en/latest/

Demo
----

This is taken from one of the tests:

.. code-block:: python

    import time
    import redis
    import pytest
    from dockerctx import new_container

    # First make a pytest fixture

    @pytest.fixture(scope='function')
    def f_redis():

        # This is the new thing! It's pretty clear.  The `ready_test` provides
        # a way to customize what "ready" means for each container. Here,
        # we simply pause for a bit.

        with new_container(
                image_name='redis:latest',
                ports={'6379/tcp': 56379},
                ready_test=lambda: time.sleep(0.5) or True) as container:
            yield container

    # Here is the test.  Since the fixture is at the "function" level, a fully
    # new Redis container will be created for each test that uses this fixture.
    # After the test completes, the container will be removed.

    def test_redis_a(f_redis):
        # The container object comes from the `docker` python package. Here we
        # access only the "name" attribute, but there are many others.
        print('Container %s' % f_redis.name)
        r = redis.StrictRedis(host='localhost', port=56379, db=0)
        r.set('foo', 'bar')
        assert r.get('foo') == b'bar'

Note that a brand new Redis container is created here, used within the
context of the context manager (which is wrapped into a *pytest* fixture
here), and then the container is destroyed after the context manager
exits.


In the src, there is another, much more elaborate test which

#. runs a *postgres* container;
#. waits for postgres to begin accepting connections;
#. creates a database;
#. creates tables (using the SQLAlchemy_ ORM);
#. performs database operations;
#. tears down and removes the container afterwards.

.. _SQLAlchemy: http://www.sqlalchemy.org/

