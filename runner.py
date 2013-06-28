# -*- coding: utf-8 -*-

import os
from os import path
import sys

sys.path.insert(1, path.join(path.dirname(path.realpath(__file__)), 'lib', 'ircd'))

from config import config

import logging

import gevent
import gevent.server
import gevent.monkey
import signal
gevent.monkey.patch_all()

from include.dispatcher import Dispatcher
from include.message import Message
from include.router import Router

from models import Actor
dispatcher = Dispatcher()
router = Router(gevent.socket.SHUT_RDWR)

from trac_integration import TracIntegration

class TracChatRunner:
	def __init__(self):
		self.trac = TracIntegration(path.realpath(config.get('trac', 'install_path')))
		self.log = logging.getLogger()

	def handle(self, socket, address):
		fileobj = socket.makefile('rw')
		while not Actor.by_socket(socket).disconnected:
			line = fileobj.readline()
			actor = Actor.by_socket(socket)
			try:
				msg = Message.from_string(line)
				self.log.debug('<= %s %s' % (repr(msg.target), repr(msg)))
				resp = dispatcher.dispatch(socket, msg)
				handler = None
				if msg.command in dispatcher.handlers:
					handler = dispatcher.handlers[msg.command]
				self.trac.handle_raw_message(msg, handler, actor, resp)
			except Exception, e:
				self.log.exception(e)
				if actor.is_user() and actor.get_user().registered.nick and actor.get_user().registered.user:
					resp = [
						Message(actor, 'NOTICE', 'The message your client has just sent could not be parsed or processed.'),
						Message(actor, 'NOTICE', 'If this is a problem with the server, please open an issue at:'),
						Message(actor, 'NOTICE', 'https://github.com/abesto/python-ircd'),
						Message(actor, 'NOTICE', '---'),
						Message(actor, 'NOTICE', 'The message sent by your client was:'),
						Message(actor, 'NOTICE', line.strip("\n")),
						Message(actor, 'NOTICE', 'The error was:'),
						Message(actor, 'NOTICE', str(e)),
						Message(actor, 'NOTICE', '---'),
						Message(actor, 'NOTICE', 'Closing connection.')
					]
					quit_resp = dispatcher.dispatch(socket, Message(None, 'QUIT', 'Protocol error'))
					if isinstance(quit_resp, list):
						resp += quit_resp
					else:
						resp.append(quit_resp)
				else:
					resp = Message(actor, 'ERROR')
				Actor.by_socket(socket).disconnect()

			try:
				router.send(resp)
			except Exception, e:
				self.log.exception(e)
				Actor.by_socket(socket).disconnect()

	def run(self):
		host = config.get('server', 'listen_host')
		port = config.getint('server', 'listen_port')
		self.log.info('Starting server, listening on %s:%s' % (host, port))
		self.server = gevent.server.StreamServer((host, port), self.handle)
		gevent.signal(signal.SIGTERM, self.term)
		gevent.signal(signal.SIGINT, self.term)
		self.server.serve_forever()
		
	def terminate(self):
		if 'server' in self:
			self.server.stop()
		self.term()

	def term(self):
		self.trac.cleanup()
		self.log.info('Server stopped')
