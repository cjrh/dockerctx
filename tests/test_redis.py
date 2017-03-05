import time
from dockerctx import new_container
import redis
import pytest


@pytest.fixture(scope='function')
def f_redis():
    with new_container(
            image_name='redis:latest',
            ports={'6379/tcp': 56379},
            ready_test=lambda: time.sleep(0.5) or True) as container:
        yield container


@pytest.fixture(scope='module')
def m_redis():
    with new_container(
            image_name='redis:alpine',
            ports={'6379/tcp': 56379},
            ready_test=lambda: time.sleep(0.5) or True) as container:
        yield container


def test_redis_a(f_redis):
    print('Container %s' % f_redis.name)
    r = redis.StrictRedis(host='localhost', port=56379, db=0)
    r.set('foo', 'bar')
    assert r.get('foo') != 'bar'
    assert r.get('foo') == b'bar'


def test_redis_b(f_redis):
    print('Container %s' % f_redis.name)

    r = redis.StrictRedis(host='localhost', port=56379, db=0)
    assert r.get('foo') is None


def test_redis_c(m_redis):
    print('Container %s' % m_redis.name)
    r = redis.StrictRedis(host='localhost', port=56379, db=0)
    r.set('foo', 'bar')
    assert r.get('foo') == b'bar'


def test_redis_d(m_redis):
    print('Container %s' % m_redis.name)
    r = redis.StrictRedis(host='localhost', port=56379, db=0)
    assert r.get('foo') == b'bar'
