#!/usr/bin/env python3.6
"""
The goal of this demo is to demonstrate how one sqlalchemy transaction
might get out of date if another transaction modifies the same records,
and completes before the first transaction can.

In addition to the above, this demo also demonstrates a way to bootstrap
a docker container as part of a test suite. There is a context manager
demonstrated where the postgres docker container is started, and then
a database is created, and then tables are created based on model
descriptions (via sqlalchemy), and then finally after runnning code that
uses the database, the container is destroyed.
"""
import uuid
import time
from contextlib import contextmanager
import threading
import sys


import docker
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy_utils import database_exists, create_database
import subprocess as sp
import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker, relationship
from sqllogformatter import SQLLogFormatter
from dockerctx import new_container
from functools import partial


logger = logging.getLogger(__name__)


sqllogger = logging.getLogger('sqlalchemy.engine')
sqllogger.propagate = False
handler = logging.StreamHandler(stream=sys.stdout)
sqllogger.addHandler(handler)
handler.setFormatter(SQLLogFormatter(
    fmt='%(asctime)20s %(name)s\n\n%(message)s\n',
    include_stack_info=False))
sqllogger.setLevel(logging.WARNING)


client = docker.from_env()
Base = declarative_base()


class Foo(Base):
    __tablename__ = 'foo'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    bees = relationship('Bar')

    def __repr__(self):
        return '[Foo: id={self.id} name={self.name}]'.format(**vars())


class Bar(Base):
    __tablename__ = 'bar'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    foo_id = Column(Integer, ForeignKey('foo.id'))

    def __repr__(self):
        return '[Bar: id={self.id} name={self.name} foo_id={self.foo_id}]'.format(**vars())


def pg_ready(host, port, timeout=20):
    import psycopg2
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            conn = psycopg2.connect(
                "host={host} port={port} user=postgres dbname=postgres".format(
                    **vars())
            )
            logger.debug('Connected successfully.')
            conn.close()
            return True
        except psycopg2.OperationalError as ex:
            logger.debug("Connection failed: {0}".format(ex));
        time.sleep(0.2)

    logger.error('Postgres readiness check timed out.')
    return False


def test_pg():
    with new_container(
            image_name='postgres:alpine',
            ports={'5432/tcp': 60011},
            ready_test=lambda: pg_ready('localhost', 60011)) as container:
        logger.debug(container.name)

        url = "postgres://postgres@localhost:60011/mydb"
        logger.info('create engine')
        if not database_exists(url):
            logger.info('create database')
            create_database(url)

        logger.info(database_exists(url))

        engine = create_engine(url)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with session_scope(Session) as session:
            create_data(session)

        with session_scope(Session) as session:
            r = fetch_data(session)
            logger.info(r)
            assert r.id == 1
            assert r.name == 'b1'
            assert r.foo_id == 1

        try:
            logger.info(r.name)
        except sqlalchemy.orm.exc.DetachedInstanceError:
            logger.info('Correct exception was thrown')
        else:
            logger.error('We expected to get an error, but there was no error')

        logger.info('THREADED DELETES')

        t1 = threading.Thread(
            target=delete, args=(Session, Foo, 'f1', 1), name='t1'
        )
        t2 = threading.Thread(
            target=delete, args=(Session, Foo, 'f1', 3), name='t2'
        )

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        with session_scope(Session) as session:
            r = fetch_data(session)
            logger.info(r)
            assert r.id == 1
            assert r.name == 'b1'
            assert r.foo_id is None

        logger.info('Complete')


def delete(Session, model=Foo, name='f1', sleep_before=0, sleep_after=0):
    thread = threading.current_thread().name
    logger.info('Entering delete: %s', thread)
    with session_scope(Session) as session:
        q = session.query(model).filter(model.name == name)
        logger.info('thread %s: query %s', thread, q)
        record = q.first()
        logger.info('thread %s: record %s', thread, record)
        time.sleep(sleep_before)
        logger.info('Deleting record')
        session.delete(record)
    time.sleep(sleep_after)
    logger.info('Leaving delete: %s', thread)


def create_data(session: sqlalchemy.orm.Session):
    f1 = Foo(name='f1')
    session.add(f1)
    session.commit()
    b2 = Bar(name='b2', foo_id=f1.id)
    b1 = Bar(name='b1', foo_id=f1.id)
    session.add(b1)
    session.add(b2)
    session.commit()


def fetch_data(session: sqlalchemy.orm.Session):
    q = session.query(Bar).filter(Bar.name == 'b1')
    logger.info(q)
    record = q.first()
    logger.info(record)
    return record


@contextmanager
def session_scope(session_cls):
    """Provide a transactional scope around a series of operations."""
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)20s %(message)s thread:%(threadName)s',
        stream=sys.stdout
    )
    test_pg()
