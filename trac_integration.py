# -*- coding: utf-8 -*-

from trac.env import open_environment
from trac.wiki import model

import datetime

from commands.privmsg import PrivmsgCommand
from models.channel import Channel

def is_error(response):
    if isinstance(response, list):
        response = response[0]
    try:
        number = float(response.command)
        return number >= 400 and number < 600
    except ValueError:
        return False

class TracIntegration:
    def __init__(self, install_path):
        self.env = open_environment(install_path)
        self.channel_messages = {}
    
    def handle_raw_message(self, message, command, actor, response):
        if not isinstance(command, PrivmsgCommand):
            return
        if is_error(response):
            return
        if not actor.is_user():
            return
        user = actor.get_user()
        receivers = message.parameters[0].split(',')
        for receiver in receivers:
            self._handle_privmsg_to_channel(message, receiver, user)

    def _handle_privmsg_to_channel(self, message, receiver, user):
        if not Channel.exists(receiver):
            return
        channel = Channel.get(receiver)
        msg_content = message.parameters[-1]
        message = "[%s] <%s>: %s" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), user.nickname, msg_content)
        self._message(channel.name, message)
    
    def _archive_messages(self, channel):
        if not channel in self.channel_messages or len(self.channel_messages[channel]) == 0:
            return
        page_name = 'ChatHistory/'+channel
        page = model.WikiPage(self.env, page_name)
        if not page.exists:
            page.text = '== '+channel+' ==\n'
        for message in self.channel_messages[channel]:
            page.text += '\n'+message+' [[BR]]'
        page.save('ChatRobot', 'Update '+datetime.datetime.utcnow().isoformat(), 'localhost')
        self.channel_messages[channel] = []
    
    def _message(self, channel, message):
        if not channel in self.channel_messages:
             self.channel_messages[channel] = []
        self.channel_messages[channel].append(message)
        if len(self.channel_messages[channel]) > 20:
            self._archive_messages(channel)
    
    def cleanup(self):
        for channel in self.channel_messages:
            self._archive_messages(channel)