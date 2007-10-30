from twisted.python import log
from twisted.internet import protocol, reactor, error
from twisted.words.xish import domish
from twisted.words.protocols.jabber import client
import struct
import sha

STREAM_INITIATE_START = "/iq[@type='set']/si[@xmlns='http://jabber.org/protocol/si']"
STREAM_INITIATE_FILETRANSFER_START = "/iq[@type='set']/si[@xmlns='http://jabber.org/protocol/si'][@profile='http://jabber.org/protocol/si/profile/file-transfer']"

# JEP65ConnectionReceive is for accepting incoming XEP65 proxy requests
# JEP65ConnectionSend is for initiating connections to XEP65 server
from pymsnft import JEP65ConnectionReceive, JEP65ConnectionSend


def no_valid_streams_stanza(iq):
    new_iq = domish.Element(('jabber:client', 'iq'))
    new_iq['to'] = iq['from']
    new_iq['id'] = iq['id']
    new_iq['type'] = 'error'
    new_iq.addElement("error")
    new_iq.error['code'] = '400'
    new_iq.error['type'] = 'cancel'
    new_iq.error.addElement('bad-request', 'urn:ietf:params:xml:ns:xmpp-stanzas')
    new_iq.error.addElement('no-valid-streams', 'http://jabber.org/protocol/si')
    return new_iq

def profile_not_understood(iq):
    new_iq = domish.Element(('jabber:client', 'iq'))
    new_iq['to'] = iq['from']
    new_iq['id'] = iq['id']
    new_iq['type'] = 'error'
    new_iq.addElement("error")
    new_iq.error['code'] = '400'
    new_iq.error['type'] = 'cancel'
    new_iq.error.addElement('bad-request', 'urn:ietf:params:xml:ns:xmpp-stanzas')
    new_iq.error.addElement('bad-profile', 'http://jabber.org/protocol/si')
    return new_iq

def reject_stream_initiation(iq):
    new_iq = domish.Element(('jabber:client', 'iq'))
    new_iq['to'] = iq['from']
    new_iq['id'] = iq['id']
    new_iq['type'] = 'error'
    new_iq.addElement("error")
    new_iq.error['code'] = '403'
    new_iq.error['type'] = 'cancel'
    new_iq.error.addElement('forbidden', 'urn:ietf:params:xml:ns:xmpp-stanzas')
    new_iq.error.addElement('text', 'urn:ietf:params:xml:ns:xmpp-stanzas', "Offer declined")
    return new_iq

class StreamInitiation:
    def __init__(self, entity):
        self._entity = entity
        self._entity.disco.addFeature('http://jabber.org/protocol/si', self)
        self._entity.iq_set_hooks.addObserver("/si[@xmlns='http://jabber.org/protocol/si']", self.onStreamInitiateRequest)
        self.streamProfiles = {}
    def onStreamInitiateRequest(self, iq):
        log.msg("onStreamInitiateRequest")
        if iq.si['profile'] not in self.streamProfiles:
            self._entity._xmlstream.send(profile_not_understood(iq))
            return
        log.msg("Understand profile..")
        self.streamProfiles[iq.si['profile']](iq) # pass to relevant stream profile handler
        log.msg("back from handler")
    def addStreamProfile(self, profile, callback):
        self.streamProfiles[profile] = callback

class FTSend:
    def __init__(self, entity, to, startTransfer, cancelTransfer, filename, filesize):
        self.startTransfer = startTransfer
        self.cancelTransfer = cancelTransfer
        self.filename = filename
        self.filesize = filesize
        self.entity = entity
    def accept(self, legacyFileSend):
        self.startTransfer(legacyFileSend)
        self.cleanup()
    def reject(self):
        self.cancelTransfer()
        self.cleanup()
    def cleanup(self):
        del self.startTransfer, self.cancelTransfer

class FileTransfer:
    SUPPORTED_STREAM_METHODS = [
        # in preference order..
            'http://jabber.org/protocol/bytestreams',
            #'jabber:iq:oob',
            #'http://jabber.org/protocol/ibb',
            ]
    def __init__(self, entity, si):
        self._entity = entity
        self._si = si
        self._entity.disco.addFeature('http://jabber.org/protocol/si/profile/file-transfer', self)
        self._entity.disco.addFeature('http://jabber.org/protocol/bytestreams', self)
        #self._entity.hook_iq_set("/si[@xmlns='http://jabber.org/protocol/si'][@profile='http://jabber.org/protocol/si/profile/file-transfer']", self.onFileTransfer)
        self._si.addStreamProfile('http://jabber.org/protocol/si/profile/file-transfer', self.onFileTransfer)

        self._entity.iq_set_hooks.addObserver("/query[@xmlns='http://jabber.org/protocol/bytestreams']", self.onByteStreamInitiate)

        self.sessions = {}

    def onAcceptFile(self, fileName, fileSize, fromJid):
        return True

    def onFileTransfer(self, iq):
        def errOut():
            pass
       # not finished yet by a long shot
        size = iq.si.file['size']
        name = iq.si.file['name']
        sid = iq.si['id']
        stream_methods = [str(s.value) for s in iq.si.feature.x.field.elements()]

        use_method = None
        for ssm in self.SUPPORTED_STREAM_METHODS:
            if ssm in stream_methods:
                use_method = ssm
                break

        if not use_method:
            self._entity._xmlstream.send(no_valid_streams_stanza(iq))
            return
        
        if not hasattr(self._entity, 'recv_file'):
            self._entity._xmlstream.send(reject_stream_initiation(iq))
            return

        # we could deny the request here by sending a reject_stream_initiation()
        if not self.onAcceptFile(iq.si.file['name'], int(iq.si.file['size']), iq['from']):
            self._entity._xmlstream.send(reject_stream_initiation(iq))
            return

        def startTransfer(consumer):
            new_iq = domish.Element(('jabber:client', 'iq'))
            new_iq['type'] = 'result'
            new_iq['id'] = iq['id']
            new_iq['to'] = iq['from']

            # response with stream-method
            new_iq.addElement('si', 'http://jabber.org/protocol/si')
            new_iq.si['id'] = sid
            new_iq.si.addElement('feature', 'http://jabber.org/protocol/feature-neg')
            new_iq.si.feature.addElement('x', 'jabber:x:data')
            new_iq.si.feature.x['type'] = 'submit'
            new_iq.si.feature.x.addElement("field")['var'] = 'stream-method'
            new_iq.si.feature.x.field.addElement("value", None, ssm)
            self._entity._xmlstream.send(new_iq)
            self.sessions[(iq['from'], sid)] = consumer
        fs = FTSend(self._entity, iq['from'], startTransfer, errOut, name, size)
        rf = self._entity.recv_file(name, size)
        fs.accept(rf)

    def onByteStreamInitiate(self, iq):
        sid = iq.query['sid']
        def get_streamhost(e):
            result = {}
            result['jid'] = e.getAttribute('jid')
            result['host'] = e.getAttribute('host')
            result['port'] = e.getAttribute('port')
            result['zeroconf'] = e.getAttribute('zeroconf')
            return result
        host_list = [get_streamhost(e) for e in iq.query.elements()]

        def validStreamHost(host):
            for streamhost in host_list:
                if streamhost['host'] == host:
                    streamhost_jid = streamhost['jid']
                    break
            else:
                return # couldn't find a jid for this host
            for connector in f.connectors:
                try:
                    connector.stopConnecting()
                except error.NotConnectingError:
                    pass
            if f.streamHostTimeout:
                f.streamHostTimeout.cancel()
                f.streamHostTimeout = None

            shiq = domish.Element(("jabber:client", "iq"))
            shiq['id'] = iq['id']
            shiq['to'] = iq['from']
            shiq['type'] = 'result'
            shiq.addElement("query", "http://jabber.org/protocol/bytestreams")
            s = shiq.query.addElement("streamhost-used")
            #iq.query['sid'] = f.stream_id
            s['jid'] = streamhost_jid
            self._entity._xmlstream.send(shiq)

        consumer = self.sessions.pop((iq['from'], sid), None)

        if not consumer:
            pass # return error
            return

        f = protocol.ClientFactory()
        f.protocol = JEP65ConnectionSend
        f.consumer = consumer
        f.hash = sha.new(sid + iq['from'] + iq['to']).hexdigest()
        f.madeConnection = validStreamHost
        f.connectors = []
        f.streamHostTimeout = reactor.callLater(120, consumer.error)
        for streamhost in host_list:
            if streamhost['host'] and streamhost['port']:
                f.connectors.append(reactor.connectTCP(streamhost['host'], int(streamhost['port']), f))

