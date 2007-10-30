# Copyright 2005-2006 James Bunton <james@delx.cjb.net>
# Licensed for distribution under the GPL version 2, check COPYING for details

from twisted.internet import protocol
from twisted.words.xish.domish import Element
import random
import sys


#def doRateLimit(setConsumer, consumer):
#	try:
#		rateLimit = int(config.ftRateLimit)
#	except ValueError:
#		rateLimit = 0
#	if rateLimit > 0:
#		throttler = Throttler(consumer, rateLimit)
#		setConsumer(throttler)
#	else:
#		setConsumer(consumer)

# SOCKS5

import socks5
import struct

# this is the class for initiating a connection to a XEP65 proxy
class JEP65ConnectionSend(protocol.Protocol):
	STATE_INITIAL = 1
	STATE_WAIT_AUTHOK = 2
	STATE_WAIT_CONNECTOK = 3
	STATE_READY = 4

	def __init__(self):
		self.state = self.STATE_INITIAL
		self.buf = ""
	
	def connectionMade(self):
		self.transport.write(struct.pack("!BBB", 5, 1, 0))
		self.state = self.STATE_WAIT_AUTHOK
	
	def connectionLost(self, reason):
		if self.state == self.STATE_READY:
			self.factory.consumer.close()
		else:
			self.factory.consumer.error()
	
	def _waitAuthOk(self):
		ver, method = struct.unpack("!BB", self.buf[:2])
		if ver != 5 or method != 0:
			self.transport.loseConnection()
			return
		self.buf = self.buf[2:] # chop
		
		# Send CONNECT request
		length = len(self.factory.hash)
		self.transport.write(struct.pack("!BBBBB", 5, 1, 0, 3, length))
		self.transport.write("".join([struct.pack("!B" , ord(x))[0] for x in self.factory.hash]))
		self.transport.write(struct.pack("!H", 0))
		self.state = self.STATE_WAIT_CONNECTOK
	
	def _waitConnectOk(self):
		ver, rep, rsv, atyp = struct.unpack("!BBBB", self.buf[:4])
		if not (ver == 5 and rep == 0):
			self.transport.loseConnection()
			return
		
		self.state = self.STATE_READY
		self.factory.madeConnection(self.transport.addr[0])
	
	def dataReceived(self, buf):
		if self.state == self.STATE_READY:
			self.factory.consumer.write(buf)

		self.buf += buf
		if self.state == self.STATE_WAIT_AUTHOK:
			self._waitAuthOk()
		elif self.state == self.STATE_WAIT_CONNECTOK:
			self._waitConnectOk()
		
# this is the socks5 server protocol, for an incoming JEP65 bytestreams connection
class JEP65ConnectionReceive(socks5.SOCKSv5):
    def __init__(self, listener):
        socks5.SOCKSv5.__init__(self)
        self.listener = listener
        self.supportedAuthMechs = [socks5.AUTHMECH_ANON]
        self.supportedAddrs = [socks5.ADDR_DOMAINNAME]
        self.enabledCommands = [socks5.CMD_CONNECT]
        self.addr = ""

    def connectRequested(self, addr, port):
        self.transport.close = self.transport.loseConnection

        # Check for special connect to the namespace -- this signifies that
        # the client is just checking that it can connect to the streamhost
        if addr == 'http://jabber.org/protocol/bytestreams': # disco.S5B
            self.connectCompleted(addr, 0)
            self.transport.loseConnection()
            return

        self.addr = addr

        if self.listener.isActive(addr):
            self.sendErrorReply(socks5.REPLY_CONN_NOT_ALLOWED)
            return

        if self.listener.addConnection(addr, self):
            self.connectCompleted(addr, 0)
        else:
            self.sendErrorReply(socks5.REPLY_CONN_REFUSED)

    def connectionLost(self, reason):
        if self.state == socks5.STATE_CONNECT_PENDING:
            self.listener.removePendingConnection(self.addr, self)
        else:
            self.transport.unregisterProducer()
            if self.peersock != None:
                self.peersock.peersock = None
                self.peersock.transport.unregisterProducer()
                self.peersock = None
                self.listener.removeActiveConnection(self.addr)

class Proxy65(protocol.Factory):
    def __init__(self, port):
        #LogEvent(INFO)
        reactor.listenTCP(port, self)
        self.pendingConns = {}
        self.activeConns = {}
	
    def buildProtocol(self, addr):
        return JEP65ConnectionReceive(self)
	
    def isActive(self, address):
        return address in self.activeConns
	
    def activateStream(self, address):
        if address in self.pendingConns:
            olist = self.pendingConns[address]
            if len(olist) != 2:
                #LogEvent(WARN, '', "Not exactly two!")
                return

            assert address not in self.activeConns
            self.activeConns[address] = None

            if not isinstance(olist[0], JEP65ConnectionReceive):
                legacyftp = olist[0]
                connection = olist[1]
            elif not isinstance(olist[1], JEP65ConnectionReceive):
                legacyftp = olist[1]
                connection = olist[0]
            else:
                #LogEvent(WARN, '', "No JEP65Connection")
                return

            doRateLimit(legacyftp.accept, connection.transport)
        else:
            #LogEvent(WARN, '', "No pending connection.")
            pass
	
	def addConnection(self, address, connection):
		olist = self.pendingConns.get(address, [])
		if len(olist) <= 1:
			olist.append(connection)
			self.pendingConns[address] = olist
			if len(olist) == 2:
				self.activateStream(address)
			return True
		else:
			return False
	
	def removePendingConnection(self, address, connection):
		olist = self.pendingConns[address]
		if len(olist) == 1:
			del self.pendingConns[address]
		else:
			olist.remove(connection)
	
	def removeActiveConnection(self, address):
		del self.activeConns[address]

