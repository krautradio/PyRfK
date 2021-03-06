#!/usr/bin/env python


import rfk.database
import rfk
import os
from sqlalchemy import *
from sqlalchemy.orm import relationship, backref,sessionmaker, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import between
import time


Base = declarative_base()


class Streamer(Base):
    __tablename__ = 'streamer'
    streamer = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    password = Column(String)
    streampassword = Column(String)
    ban      = Column(DateTime) 

class Show(Base):
    __tablename__ = 'shows'
    show = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column('streamer', Integer(unsigned=True), ForeignKey('streamer.streamer', onupdate="CASCADE", ondelete="RESTRICT"))
    streamer = relationship('Streamer', backref='shows')
    songs = relationship('Song', backref='shows')
    name = Column(String)
    type = Column(String)
    description = Column(String)
    begin = Column(DateTime)
    end = Column(DateTime)
    
class Song(Base):
    __tablename__ = 'songhistory'
    song = Column(Integer, primary_key=True, autoincrement=True)
    show_id = Column('show', Integer(unsigned=True), ForeignKey('shows.show', onupdate="CASCADE", ondelete="RESTRICT"))
    artist = Column(String)
    title = Column(String)
    begin = Column(DateTime)
    end = Column(DateTime)

mount_relay = Table('mount_relay', Base.metadata,
     Column('mount', Integer(unsigned=True), ForeignKey('mounts.mount')),
     Column('relay', Integer(unsigned=True), ForeignKey('relays.relay'))
)

class Mount(Base):
    __tablename__ = 'mounts'
    mount = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String)
    name = Column(String)
    description = Column(String)
    type = Column(String)
    quality = Column(Integer)
    username = Column(String)
    password = Column(String)
    relays = relationship('Relay', secondary='mount_relay', backref='mounts')
    
class Relay(Base):
    __tablename__ = 'relays'
    relay = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String)
    hostname = Column(String)
    port = Column(String)
    status = Column(String)
    bandwidth = Column(Integer)
    query_method = Column(String)
    query_user = Column(String)
    query_pass = Column(String)
    
class Listener(Base):
    __tablename__ = 'listenerhistory'
    listenerhistory = Column(Integer, primary_key=True, autoincrement=True)
    mount_id = Column('mount', Integer(unsigned=True), ForeignKey('mounts.mount'))
    mount = relationship('Mount', backref='listenerhistory')
    relay_id = Column('relay', Integer(unsigned=True), ForeignKey('relays.relay'))
    relay = relationship('Relay', backref='listenerhistory')
    ip = Column(Integer)
    useragent = Column(String)
    connected = Column(DateTime)
    disconnected = Column(DateTime)
    client = Column(Integer)
    
class News(Base):
    __tablename__ = 'news'
    news = Column(Integer, primary_key=True, autoincrement=True)
    streamer_id = Column('streamer', Integer(unsigned=True), ForeignKey('streamer.streamer', onupdate="CASCADE", ondelete="RESTRICT"))
    streamer = relationship('Streamer', backref='news')
    time = Column(DateTime)
    description = Column(String)
    text = Column(Text)
    
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rfk.init(current_dir)

old_engine = create_engine("%s://%s:%s@%s/%s?charset=utf8" % (rfk.CONFIG.get('olddatabase', 'engine'),
                                                              rfk.CONFIG.get('olddatabase', 'username'),
                                                              rfk.CONFIG.get('olddatabase', 'password'),
                                                              rfk.CONFIG.get('olddatabase', 'host'),
                                                              rfk.CONFIG.get('olddatabase', 'database')))

rfk.database.init_db("%s://%s:%s@%s/%s?charset=utf8" % (rfk.CONFIG.get('database', 'engine'),
                                                              rfk.CONFIG.get('database', 'username'),
                                                              rfk.CONFIG.get('database', 'password'),
                                                              rfk.CONFIG.get('database', 'host'),
                                                              rfk.CONFIG.get('database', 'database')))


OldSession = sessionmaker(bind=old_engine)
oldsession = OldSession()

from rfk.database.base import User

def copy_users():
    streamer = oldsession.query(Streamer).yield_per(50)
    
    for olduser in streamer:
        print olduser.username
        if User.get_user(olduser.username) is None:
            user = User.add_user(olduser.username, olduser.password)
            rfk.database.session.add(user)
            rfk.database.session.flush()
    rfk.database.session.commit()
    

from rfk.database.show import Show as NShow
from rfk.database.show import UserShow
from rfk.database.track import Track
import pytz

def copy_shows():
    local = pytz.timezone('Europe/Berlin')
    shows = oldsession.query(Show).yield_per(50)
    for oldshow in shows:
        if oldshow.streamer != None:
            user = User.get_user(username=oldshow.streamer.username)
            if oldshow.type == 'UNPLANNED':
                flag = NShow.FLAGS.UNPLANNED
            elif oldshow.type == 'PLANNED':
                flag = NShow.FLAGS.PLANNED
            show = NShow(name=oldshow.name[:50],
                        description=oldshow.description,
                        flags=flag,
                        begin=local.normalize(local.localize(oldshow.begin).astimezone(pytz.utc)),
                        end=local.normalize(local.localize(oldshow.end).astimezone(pytz.utc)))
            rfk.database.session.add(show)
            rfk.database.session.flush()
            show.add_user(user)
            rfk.database.session.flush()
            rfk.database.session.commit()
            #for oldsong in oldshow.songs:
            #    begin = oldsong.begin.replace(tzinfo=local)
            #    end = oldsong.end.replace(tzinfo=local)
            #    print 'track', oldsong.end, end
            #    track = Track.new_track(show,
            #                            oldsong.artist,
            #                            oldsong.title,
            #                            begin=utc.normalize(begin.astimezone(utc)))
            #    rfk.database.session.add(track)
            #    rfk.database.session.commit()
            #    track.end_track(utc.normalize(end.astimezone(utc)))
            #    rfk.database.session.commit()

import rfk.database.streaming
import rfk.database.stats

def copy_mounts():
    relays = oldsession.query(Relay).yield_per(50)
    for oldrelay in relays:
        print oldrelay.type
        
        print oldrelay.hostname[0:15]
        try:
            relay = rfk.database.streaming.Relay.get_relay(address=oldrelay.hostname[0:15], port=oldrelay.port)
        except exc.NoResultFound:
            relay = rfk.database.streaming.Relay(address=oldrelay.hostname[0:15], port=oldrelay.port)
        
        if oldrelay.type == 'RELAY':
            relay.type = rfk.database.streaming.Relay.TYPE.RELAY
        else:
            relay.type = rfk.database.streaming.Relay.TYPE.MASTER
        relay.status = rfk.database.streaming.Relay.STATUS.UNKNOWN
        relay.admin_username = oldrelay.query_user
        relay.admin_password = oldrelay.query_pass
        relay.auth_username = 'master'
        relay.auth_password = 'master'
        relay.relay_password = 'radiowegrelayen'
        relay.relay_username = 'relay'
        rfk.database.session.add(relay)
        rfk.database.session.flush()
        for mount in oldrelay.mounts:
            try:
                stream = rfk.database.streaming.Stream.get_stream(mount=mount.path)
            except exc.NoResultFound:
                stream = rfk.database.streaming.Stream(mount=mount.path)
                stat = rfk.database.stats.Statistic(name="Listener %s" % (mount.name), identifier="lst-%s" % (mount.path,))
                rfk.database.session.add(stat)
                stream.statistic = stat
                rfk.database.session.add(stream)
            rfk.database.session.flush()
            relay.add_stream(stream)
            rfk.database.session.flush()
        rfk.database.session.commit()

import struct, socket
int2ip = lambda n: socket.inet_ntoa(struct.pack('!I', n))

def copy_listener():
    listeners = oldsession.query(Listener).yield_per(250)
    local = pytz.timezone('Europe/Berlin')
    c = 0
    cache = {}
    totallistener = rfk.database.stats.Statistic.query.filter(rfk.database.stats.Statistic.identifier == 'lst-total').one()
    for oldlistener in listeners:
        if oldlistener.relay.hostname[0:15] not in cache:
            cache[oldlistener.relay.hostname[0:15]] = {}
        
        if oldlistener.mount.path not in cache[oldlistener.relay.hostname[0:15]]:
            relay = rfk.database.streaming.Relay.get_relay(address=oldlistener.relay.hostname[0:15], port=oldlistener.relay.port)
            stream = rfk.database.streaming.Stream.get_stream(mount=oldlistener.mount.path)
            try:
                sr = relay.get_stream_relay(stream)
            except sqlalchemy.orm.exc.NoResultFound as e:
                sr = relay.add_stream(stream)
            cache[oldlistener.relay.hostname[0:15]][oldlistener.mount.path] = sr
        
        t = time.time()
        listener = rfk.database.streaming.Listener.create(int2ip(oldlistener.ip),
                                                          oldlistener.client,
                                                          oldlistener.useragent[:255],
                                                          cache[oldlistener.relay.hostname[0:15]][oldlistener.mount.path])
        listener.connect = local.normalize(local.localize(oldlistener.connected)).astimezone(pytz.utc)
        listener.disconnect = local.normalize(local.localize(oldlistener.disconnected)).astimezone(pytz.utc)
        rfk.database.session.flush()
        rfk.database.session.commit()

def calc_stats():
    """This is slow as fuck
    """
    totallistener = rfk.database.stats.Statistic.query.filter(rfk.database.stats.Statistic.identifier == 'lst-total').one()
    listeners = rfk.database.streaming.Listener.query.order_by(rfk.database.streaming.Listener.listener.desc()).yield_per(500)
    c = 0
    for listener in listeners:
        c += 1
        c1 = rfk.database.streaming.Listener.query.join(rfk.database.streaming.StreamRelay).filter(rfk.database.streaming.StreamRelay.stream == listener.stream_relay.stream,
                                                          listener.connect >= rfk.database.streaming.Listener.connect,
                                                          listener.connect < rfk.database.streaming.Listener.disconnect).count()
        c2 = rfk.database.streaming.Listener.query.join(rfk.database.streaming.StreamRelay).filter(rfk.database.streaming.StreamRelay.stream == listener.stream_relay.stream,
                                                          listener.disconnect >= rfk.database.streaming.Listener.connect,
                                                          listener.disconnect < rfk.database.streaming.Listener.disconnect).count()
        ct1 = rfk.database.streaming.Listener.query.filter(listener.connect >= rfk.database.streaming.Listener.connect,
                                                          listener.connect < rfk.database.streaming.Listener.disconnect).count()
        ct2 = rfk.database.streaming.Listener.query.filter(listener.disconnect >= rfk.database.streaming.Listener.connect,
                                                          listener.disconnect < rfk.database.streaming.Listener.disconnect).count()
        listener.stream_relay.stream.statistic.set(listener.connect,c1)
        listener.stream_relay.stream.statistic.set(listener.disconnect,c2)
        totallistener.set(listener.connect, ct1)
        totallistener.set(listener.disconnect, ct2)
        print c, c1, c2, ct1, ct2
        rfk.database.session.flush()
        rfk.database.session.commit()
    
def copy_news():
    news = oldsession.query(News).yield_per(50)
    print news
    for oldnews in news:
        user = session.query(rfk.User).filter(rfk.User.name == oldnews.streamer.username).first()
        news = rfk.News(user=user,content=oldnews.text, title=oldnews.description, time=oldnews.time)
        session.add(news)
        session.commit()

def add_misc():
    stat = rfk.database.stats.Statistic(name="Overall Listener", identifier="lst-total")
    rfk.database.session.add(stat)
    rfk.database.session.commit()

if __name__ == '__main__':
    #add_misc()
    #copy_users()
    #copy_shows()
    #copy_mounts()
    #copy_listener()
    calc_stats()
    #copy_news()
        
        
