from twisted.internet.protocol import DatagramProtocol
from twisted.internet import defer
import time
import socket
import random
import struct, md5

BINDING_REQUEST  = 0x0001
BINDING_RESPONSE = 0x0101
BINDING_ERROR    = 0x0111
SS_REQUEST  = 0x0002
SS_RESPONSE = 0x0102
SS_ERROR    = 0x0112

MAPPED_ADDRESS = 0x0001
RESPONSE_ADDRESS = 0x0002
CHANGE_REQUEST = 0x0003
SOURCE_ADDRESS = 0x0004
CHANGED_ADDRESS = 0x0005
USERNAME = 0x0006
PASSWORD = 0x0007
MESSAGE_INTEGRITY = 0x0008
ERROR_CODE = 0x0009
UNKNOWN_ATTRIBUTES = 0x000a
REFLECTED_FROM = 0x000b

STATE_UNREADY = 0
STATE_SENT_REQUEST = 1

def dump(data):
    for p in xrange(0, len(data), 16):
        print ' '.join(['%02X' % ord(x) for x in list(data[p:p+16])])

class STUN(DatagramProtocol):
    state = STATE_UNREADY
    def getBindingRequest(self):
        random.seed(time.time())
        self.transaction_id = md5.new(str(random.getrandbits(32))).digest()
        header = struct.pack('>2H', BINDING_REQUEST, 0) + self.transaction_id
        return header
    
    def startProtocol(self):
        pass

    def request(self, server, port=3478):
        self.transport.connect( socket.gethostbyname(server), port )
        self.transport.write(self.getBindingRequest())
        self.state = STATE_SENT_REQUEST
        self.result = defer.Deferred()
        return self.result
        
    def datagramReceived(self, data, (host,port)):
        type, length = struct.unpack('>2H', data[:4])
        id = data[4:20]
        if id <> self.transaction_id:
            raise "Unmatched transaction id"
        if self.state == STATE_SENT_REQUEST:
            # hopefully, this is a response
            if type == BINDING_RESPONSE:
                self.receiveBindingResponse((host, port), data[20:])
    
    def receiveBindingResponse(self, (host,port), response):
        for type, length, data in self.getAttributes(response):
            if type == MAPPED_ADDRESS:
                family, recv_port, ip_addr = struct.unpack('>xBH4s', data)
                ip_addr = socket.inet_ntoa(ip_addr)
                self.result.callback( (ip_addr, recv_port) )
            elif type == SOURCE_ADDRESS:
                pass    
    def getAttributes(self, data):
        ptr = 0
        while ptr<len(data):
            type, length = struct.unpack('>2H', data[ptr:ptr+4])
            yield type, length, data[ptr+4:ptr+4+length]
            ptr += 4+length
    def connectionRefused(self):
        print "noone listening"

if __name__ == "__main__":
    from twisted.internet import reactor
    from twisted.python import log
    import sys
    #log.startLogging(sys.stdout)
    s = STUN()
    reactor.listenUDP(0, s)
    def found( (addr,port) ):
        print "%s:%s" % (addr, port)
        reactor.stop()
    s.request('stunserver.org').addCallback(found)
    reactor.run()
    