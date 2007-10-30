import namespaces, xpaths
from twisted.words.xish import domish
from twisted.python import log

try:
    import uuid
    uuidfunc = uuid.uuid4
except ImportError:
    def UUID_GEN():
        a = 1
        while True:
            yield `a`
            a=a+1
    UG = UUID_GEN()
    uuidfunc = UG.next

namespaces.JINGLE = 'http://www.xmpp.org/extensions/xep-0166.html#ns'


namespaces.JINGLE_ICE = 'http://www.xmpp.org/extensions/xep-0176.html#ns'
namespaces.JINGLE_ICEUDP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-udp'
namespaces.JINGLE_TCETCP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-tcp'
namespaces.JINGLE_RAWUDP = 'http://www.xmpp.org/extensions/xep-0177.html#ns'
namespaces.JINGLE_FT = 'http://www.xmpp.org/extensions/xep-xxxx.html#ns'

namespaces.JINGLE_AUDIO_RTP = 'http://www.xmpp.org/extensions/xep-0167.html#ns'
namespaces.JINGLE_VIDEO_RTP = 'http://www.xmpp.org/extensions/xep-0180.html#ns'

def gen_jingle_action_xpath(act):
    #return "/iq/*[@xmlns='%s'][action='%s']" % (namespaces.JINGLE, act)
    return "/iq/*[@xmlns='%s']" % namespaces.JINGLE

xpaths.JINGLE_CONTENT_ACCEPT = gen_jingle_action_xpath("content-accept")
xpaths.JINGLE_CONTENT_ADD = gen_jingle_action_xpath("content-add")
xpaths.JINGLE_CONTENT_MODIFY = gen_jingle_action_xpath("content-modify")
xpaths.JINGLE_CONTENT_REMOVE = gen_jingle_action_xpath("content-remove")

xpaths.JINGLE_SESSION_ACCEPT = gen_jingle_action_xpath("session-accept")
xpaths.JINGLE_SESSION_INFO = gen_jingle_action_xpath("session-info")
xpaths.JINGLE_SESSION_INITIATE = gen_jingle_action_xpath("session-initiate")
xpaths.JINGLE_SESSION_TERMINATE = gen_jingle_action_xpath("session-terminate")

xpaths.JINGLE_TRANSPORT_INFO = gen_jingle_action_xpath("transport-info")


class JingleTransport:
    pass

class JingleTransportTCEUDP(JingleTransport):
    pass

class JingleTransportICETCP(JingleTransport):
    pass

class JingleTransportRAWUDP(JingleTransport):
    pass


class Jingle:
    def _jingleIq(self, type="set"):
        iq = self._entity.getIQ(type)
        iq.addElement((namespaces.JINGLE, "jingle"))
        return iq

    def getUniqueSid(self):
        return uuidfunc()

    def __init__(self, entity):
        self._entity = entity
        self.sessions = {}
        
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_INITIATE, self.onSessionInitiate)
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_ACCEPT, self.onSessionAccept)
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_TERMINATE, self.onSessionTerminate)
        
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_ACCEPT, self.onContentAccept)
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_ADD, self.onContentAdd)
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_MODIFY, self.onContentModify)
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_REMOVE, self.onContentRemove)
        
        self._entity.disco.addFeature(namespaces.JINGLE)
        self._entity.disco.addFeature(namespaces.JINGLE_RAWUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_ICEUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_ICEUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_AUDIO_RTP)
        self._entity.disco.addFeature(namespaces.JINGLE_VIDEO_RTP)
        self._entity.disco.addFeature(namespaces.JINGLE_FT)
    
    def onSessionInitiate(self, iq):
        "Called when someone wants to initiate a jingle session with us"
        pass
    def onSessionAccept(self, iq):
        "Called when someone accepts our session invitation"
        log.msg('onSessionAccept: %s' % iq.toXml())
        sid = iq.jingle['sid']
        result_iq = self._entity.getIQ(type="result")
        result_iq['id'] = iq['id']
        self.sessions[sid]['responder'] = iq.jingle['responder']
        self.sessions[sid]['status'] = 'ACTIVE'
        result_iq.send(iq.jingle['responder'])
        
    def onSessionTerminate(self, iq):
        "Called when someone wants to terminate our session"
        log.msg('onSessionTerminate: %s' % iq.toXml())
        self.sessions[iq.jingle['sid']]['status'] = 'TERMINATED'
        log.msg('session terminated')
        del self.sessions[iq.jingle['sid']]
    
    def onContentAccept(self, iq):
        "Called when someone accepts content"
        log.msg("content-accept")
    def onContentAdd(self, iq):
        "Called when someone wants to add a content stream"
        pass
    def onContentModify(self, iq):
        "Called when someone wants to modify a content stream"
        pass
    def onContentRemove(self, iq):
        "Called when someone wants to remove a content stream"
        log.msg('onContentRemove %s' % iq.toXml())
        if iq.jingle['sid'] not in self.sessions:
            log.msg("Non existent SID: %s" % iq.toXml())
        pass
    
    def initiateSession(self, full_jid, streams):
        log.msg("trying to initiate jingle session with %s" % full_jid)
        iq = self._jingleIq()
        iq.jingle['action'] = 'session-initiate'
        iq.jingle['initiator'] = self._entity._jid.full()
        sid = self.getUniqueSid()
        iq.jingle['sid'] = sid
        if 'audio' in streams:
            content = iq.jingle.addElement((None, "content"))
            content['name'] = 'this-is-the-audio-content'
            content['creator'] = 'initiator'

            desc = content.addElement((namespaces.JINGLE_AUDIO_RTP, 'description'))
            t = desc.addElement((None, 'payload-type'))
            t['id'] = '96'
            t['name'] = 'speex'
            t['clockrate'] = '16000'

            t = desc.addElement((None, 'payload-type'))
            t['id'] = '97'
            t['name'] = 'speex'
            t['clockrate'] = '8000'
            content.addElement((namespaces.JINGLE_ICEUDP, 'transport'))
        #if 'video' in streams:
        #    content = iq.jingle.addElement((None, "content"), None, {
        #        'name': 'this-is-the-video-content',
        #        'creator': 'initiator',
        #        })
        #    content.addElement((namespaces.JINGLE_VIDEO_RTP, 'description'))
        #    content.addElement((namespaces.JINGLE_ICEUDP, 'transport'))

        self.sessions[sid] = {'status': 'requested', 'responder': full_jid}
        def f(i):
            if i['type'] == 'result':
                self.sessions[sid]['status'] = 'pending'
            elif i['type'] == 'error':
                fc = i.error.firstChildElement()
                if fc.name == 'service-unavailable':
                    # initiator unknown to receiver / receiver does not support jingle
                    pass
                elif fc.name == 'redirect':
                    # receiver redirection
                    pass
                elif fc.name == 'feature-not-implemented':
                    # unsupported something
                    # i.error will also contain <unsupported-content/> or <unsupported-transports/>
                    pass
                elif fc.name == 'bad-request':
                    # initiation request malformed
                    pass
        iq.addCallback(f)
        log.msg("sending %s" % iq.toXml())
        iq.send(full_jid)

    def terminateSession(self, sid, reason=None):
        iq = self._jingleIq()
        iq.jingle['action'] = 'session-terminate'
        iq.jingle['initiator'] = self._entity._jid.full()
        if reason:
            iq.jingle['reason'] = reason
        iq.jingle['sid'] = sid
        iq.send(self.sessions[sid]['responder'])
        del self.sessions[sid]
