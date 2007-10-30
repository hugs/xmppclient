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

namespaces.JINGLE = 'http://www.google.com/session'


namespaces.JINGLE_ICE = 'http://www.xmpp.org/extensions/xep-0176.html#ns'
namespaces.JINGLE_ICEUDP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-udp'
namespaces.JINGLE_TCETCP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-tcp'
namespaces.JINGLE_RAWUDP = 'http://www.xmpp.org/extensions/xep-0177.html#ns'
namespaces.JINGLE_FT = 'http://www.xmpp.org/extensions/xep-xxxx.html#ns'

namespaces.JINGLE_AUDIO_RTP = 'http://www.xmpp.org/extensions/xep-0167.html#ns'
namespaces.JINGLE_VIDEO_RTP = 'http://www.xmpp.org/extensions/xep-0180.html#ns'

namespaces.JINGLE_PHONE = 'http://www.google.com/session/phone'

xpaths.JINGLE_IQ = "/iq/*[@xmlns='%s']" % namespaces.JINGLE
def gen_jingle_action_xpath(act):
    return "/iq/*[@xmlns='%s'][action='%s']" % (namespaces.JINGLE, act)
#return "/iq/*[@xmlns='%s']" % namespaces.JINGLE


#xpaths.JINGLE_CONTENT_ACCEPT = gen_jingle_action_xpath("content-accept")
#xpaths.JINGLE_CONTENT_ADD = gen_jingle_action_xpath("content-add")
#xpaths.JINGLE_CONTENT_MODIFY = gen_jingle_action_xpath("content-modify")
#xpaths.JINGLE_CONTENT_REMOVE = gen_jingle_action_xpath("content-remove")

#xpaths.JINGLE_SESSION_ACCEPT = gen_jingle_action_xpath("session-accept")
#xpaths.JINGLE_SESSION_INFO = gen_jingle_action_xpath("session-info")
#xpaths.JINGLE_SESSION_INITIATE = gen_jingle_action_xpath("session-initiate")
#xpaths.JINGLE_SESSION_TERMINATE = gen_jingle_action_xpath("session-terminate")

#xpaths.JINGLE_TRANSPORT_INFO = gen_jingle_action_xpath("transport-info")


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
        
        self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_IQ, self.jingleDispatcher)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_INITIATE, self.onSessionInitiate)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_ACCEPT, self.onSessionAccept)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_TERMINATE, self.onSessionTerminate)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_SESSION_INFO, self.onSessionInfo)
        
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_ACCEPT, self.onContentAccept)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_ADD, self.onContentAdd)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_MODIFY, self.onContentModify)
        #self._entity.iq_set_hooks.addObserver(xpaths.JINGLE_CONTENT_REMOVE, self.onContentRemove)
        
        self._entity.disco.addFeature(namespaces.JINGLE)
        self._entity.disco.addFeature(namespaces.JINGLE_RAWUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_ICEUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_ICEUDP)
        self._entity.disco.addFeature(namespaces.JINGLE_AUDIO_RTP)
        self._entity.disco.addFeature(namespaces.JINGLE_VIDEO_RTP)
        self._entity.disco.addFeature(namespaces.JINGLE_FT)
    
    def jingleDispatcher(self, iq):
        log.msg("Jingle Dispatcher: %s" % iq.toXml())
        e = iq.firstChildElement()
        act = '%s-%s' % (e.name, e['type'])
        if act == 'session-initiate':
            self.onSessionInitiate(iq)
        elif act == 'session-terminate':
            self.onSessionTerminate(iq)
        elif act == 'session-accept':
            self.onSessionAccept(iq)
        elif act == 'session-info':
            self.onSessionInfo(iq)
        elif act == 'session-candidates':
            self.onSessionCandidates(iq)

        elif act == 'content-accept':
            self.onContentAccept(iq)
        elif act == 'content-add':
            self.onContentAdd(iq)
        elif act == 'content-remove':
            self.onContentRemove(iq)
        elif act == 'content-modify':
            self.onContentModify(iq)

        elif act == 'transport-info':
            self.onTransportInfo(iq)


    def onSessionInitiate(self, iq):
        "Called when someone wants to initiate a jingle session with us"
        log.msg("SESSION INITIATE REQUEST")
        new_iq = self._entity.getIQ(type="result")
        new_iq['id'] = '' # iq['id']
        new_iq.send(iq['from'])
        del new_iq['id']
        new_iq.send(iq['from'])
        self.sessions[iq.session['id']] = {'status': 'PENDING', 'responder': iq['from'], 'initiator': iq.session['initiator']}
        self.sendCandidates(iq.session['id'])

        accept = self._entity.getIQ()
        accept.addElement((namespaces.JINGLE, "session"))
        accept.session['id'] = iq.session['id']
        accept['type'] = 'accept'
        accept['initiator'] = self.sessions[iq.session['id']]['initiator']
        desc = accept.addElement((namespaces.JINGLE_PHONE, "description"))
        desc.addElement((None, 'payload-type'))
        desc['id'] = '110'
        desc['name'] = 'speex'
        desc = accept.addElement((namespaces.JINGLE_PHONE, "description"))
        desc.addElement((None, 'payload-type'))
        desc['id'] = '0'
        desc['name'] = 'PCMU'
        accept.send(iq['from'])

    def onSessionCandidates(self, iq):
        log.msg("GOT SOME CANDIDATES")

    def onSessionAccept(self, iq):
        "Called when someone accepts our session invitation"
        log.msg('onSessionAccept: %s' % iq.toXml())
        sid = iq.jingle['sid']
        result_iq = self._entity.getIQ(type="result")
        result_iq['id'] = iq['id']
        self.sessions[sid]['responder'] = iq.jingle['responder']
        self.sessions[sid]['status'] = 'ACTIVE'
        result_iq.send(iq.jingle['responder'])
        
    def onSessionInfo(self, iq):
        log.msg("onSessionInfo")
        pass
    def onSessionTerminate(self, iq):
        "Called when someone wants to terminate our session"
        log.msg('onSessionTerminate: %s' % iq.toXml())
        sess = iq.firstChildElement()
        if sess['id'] in self.sessions:
            self.sessions[sess['id']]['status'] = 'TERMINATED'
            log.msg('session terminated')
            del self.sessions[iq.session['id']]
        else:
            log.msg("tried to terminate non-existent session %s" % sess['id'])
    
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
        iq = self._entity.getIQ()
        iq.addElement((namespaces.JINGLE, 'session'))
        iq.session['type'] = 'initiate'
        #iq.jingle['action'] = 'session-initiate'
        #iq.jingle['initiator'] = self._entity._jid.full()
        iq.session['initiator'] = self._entity._jid.full()
        sid = self.getUniqueSid()
        #iq.jingle['sid'] = sid
        iq.session['id'] = sid
        if 'audio' in streams:
            desc = iq.session.addElement((namespaces.JINGLE_PHONE, 'description'))
            #content = desc.addElement((None, "content"))
            #content['name'] = 'this-is-the-audio-content'
            #content['creator'] = 'initiator'

            t = desc.addElement((None, 'payload-type'))
            t['id'] = '110'
            t['name'] = 'speex'

        #if 'video' in streams:
        #    content = iq.jingle.addElement((None, "content"), None, {
        #        'name': 'this-is-the-video-content',
        #        'creator': 'initiator',
        #        })
        #    content.addElement((namespaces.JINGLE_VIDEO_RTP, 'description'))
        #    content.addElement((namespaces.JINGLE_ICEUDP, 'transport'))

        self.sessions[sid] = {'status': 'requested', 'responder': full_jid}
        def f(i):
            log.msg("CALLBACK")
            if i['type'] == 'result':
                self.sessions[sid]['status'] = 'pending'
                log.msg("RESULT %s" % i.toXml())

                self.sendCandidates(sid)
            elif i['type'] == 'error':
                log.msg("ERROR")
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

    def sendCandidates(self, sid):
        iq = self._entity.getIQ()
        iq.addElement((namespaces.JINGLE, 'session'))
        iq.session['initiator'] = self._entity._jid.full()
        iq.session['type'] = 'candidates'
        iq.session['id'] = sid

        c = iq.session.addElement((None, 'candidate'))
        c['username'] = 'hello'
        c['password'] = 'hello'
        c['preference'] = '1'
        c['type'] = 'local'
        c['address'] = '192.168.2.22'
        c['port'] = '919191'
        c['protocol'] = 'udp'
        c['name'] = 'rtp'
        c['generation'] = '0'
        c['network'] = 'eth1'
        
        log.msg("SENDING CANDIDATES %s" % iq.toXml())
        iq.send(self.sessions[sid]['responder'])
    def terminateSession(self, sid, reason=None):
        iq = self._jingleIq()
        iq.jingle['action'] = 'session-terminate'
        iq.jingle['initiator'] = self._entity._jid.full()
        if reason:
            iq.jingle['reason'] = reason
        iq.jingle['sid'] = sid
        iq.send(self.sessions[sid]['responder'])
        del self.sessions[sid]
