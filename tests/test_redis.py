import time
from dockerctx import new_container, get_open_port
import redis
import pytest


@pytest.fixture(scope='function')
def f_redis():
    port = get_open_port()
    with new_container(
            image_name='redis:latest',
            ports={'6379/tcp': port},
            ready_test=lambda: time.sleep(0.5) or True) as container:
        yield container, port


@pytest.fixture(scope='module')
def m_redis():
    port = get_open_port()
    with new_container(
            image_name='redis:alpine',
            ports={'6379/tcp': port},
            ready_test=lambda: time.sleep(0.5) or True) as container:
        yield container, port


def test_redis_a(f_redis):
    container, port = f_redis
    print('Container %s' % container.name)
    r = redis.StrictRedis(host='localhost', port=port, db=0)
    r.set('foo', 'bar')
    assert r.get('foo') == b'bar'


def test_redis_b(f_redis):
    container, port = f_redis
    print('Container %s' % container.name)
    r = redis.StrictRedis(host='localhost', port=port, db=0)
    assert r.get('foo') is None


def test_redis_c(m_redis):
    container, port = m_redis
    print('Container %s' % container.name)
    r = redis.StrictRedis(host='localhost', port=port, db=0)
    r.set('foo', 'bar')
    assert r.get('foo') == b'bar'


def test_redis_d(m_redis):
    container, port = m_redis
    print('Container %s' % container.name)
    r = redis.StrictRedis(host='localhost', port=port, db=0)
    assert r.get('foo') == b'bar'


@pytest.mark.parametrize('value', list(range(10)))
def test_redis_many(m_redis, value):
    container, port = m_redis
    print('Container %s' % container.name)
    r = redis.StrictRedis(host='localhost', port=port, db=0)
    r.set('number', value)
    r.set_response_callback('GET', int)
    assert r.get('number') == value
