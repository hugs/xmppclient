from twisted.words.protocols.jabber import jid, client
from twisted.words.xish import domish
from twisted.internet import reactor
from twisted.internet.utils import getProcessOutput
from twisted.python import log
import sys

from utils import messageStanza
from client import BasicJabberClient, RosterJabberClient
from adhoc import *

import xpaths, namespaces

class BotMixIn:
    def initBot(self, private=True, whitelist=[]):
        self.private = private
        self._whitelist = whitelist
        #self.adhoc = adhoc.AdHocCommands(self, commands, self.whitelistMatch)
        self.message_hooks.addObserver('//event/RECEIVE', self.receiveMessage)
        
    def whitelistMatch(self, testJID):
        "Check whether testJID is allowed to send commands to this bot"
        if not self.private:
            return True
        if testJID.userhost() == self._jid.userhost():
            return True # self contact
        if testJID.full() in self._whitelist:
            return True
        if testJID.userhost() in self._whitelist:
            return True
        return False
    
    def receiveMessage(self, msg):
        cmdline = str(msg.body)
        jid_from = jid.internJID(msg['from'])
        if self.whitelistMatch(jid_from):
            self.receiveAuthorizedCommand(msg)
    
    def receiveAuthorizedCommand(self, msg):
        "Called when we receive a message from a whitelisted address.. override in your own class"
        m = messageStanza(msg['from'], 'whitelisted :)', 'normal')
        self._xmlstream.send(m)

    def receiveUnauthorizedCommand(self, msg):
        "Called when we receive a message from someone we don't trust.. override in your own class"
        #m = messageStanza(msg['from'], 'Unauthorized', 'normal')
        #self._xmlstream.send(m)
        pass


class BasicJabberBot(BasicJabberClient, BotMixIn):
    def __init__(self, myJID, myPassword, private=True, whitelist=[]):
        BasicJabberClient.__init__(self, myJID, myPassword, 'bot')
        self.initBot(private=private, whitelist=whitelist)
    
class RosterJabberBot(RosterJabberClient, BotMixIn):
    def __init__(self, myJID, myPassword, private=True, whitelist=[]):
        RosterJabberClient.__init__(self, myJID, myPassword, 'bot')
        self.initBot(private=private, whitelist=whitelist)
    
    def onSubscribe(self, presence):
        self.allowSubscribe(presence)
