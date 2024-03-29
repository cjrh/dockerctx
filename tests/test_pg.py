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
import time
import threading
import sys


import docker
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy_utils import database_exists, create_database
import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker, relationship
from sqllogformatter import SQLLogFormatter
from dockerctx import new_container, pg_ready, session_scope, get_open_port


logger = logging.getLogger(__name__)


sqllogger = logging.getLogger('sqlalchemy.engine')
sqllogger.propagate = False
handler = logging.StreamHandler(stream=sys.stdout)
sqllogger.addHandler(handler)
handler.setFormatter(SQLLogFormatter(
    fmt='%(asctime)20s %(name)s\n\n%(message)s\n',
    include_stack_info=False))
sqllogger.setLevel(logging.WARNING)


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


def test_pg():
    port = get_open_port()
    with new_container(
            image_name='postgres:alpine',
            ports={'5432/tcp': port},
            ready_test=lambda: pg_ready('127.0.0.1', port),
            # Travis CI fails otherwise :`(
            docker_api_version='1.24',
            environment={'POSTGRES_PASSWORD': 'password'}
    ) as container:
        logger.debug(container.name)

        url = "postgresql://postgres:password@127.0.0.1:%d/mydb" % port
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


def create_data(session):
    f1 = Foo(name='f1')
    session.add(f1)
    session.commit()
    b2 = Bar(name='b2', foo_id=f1.id)
    b1 = Bar(name='b1', foo_id=f1.id)
    session.add(b1)
    session.add(b2)
    session.commit()


def fetch_data(session):
    q = session.query(Bar).filter(Bar.name == 'b1')
    logger.info(q)
    record = q.first()
    logger.info(record)
    return record
