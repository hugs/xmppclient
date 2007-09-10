import namespaces, xpaths
from twisted.words.xish import domish

namespaces.JINGLE = 'http://www.xmpp.org/extensions/xep-0166.html#ns'

namespaces.JINGLE_ICEUDP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-udp'
namespaces.JINGLE_TCETCP = 'http://www.xmpp.org/extensions/xep-0176.html#ns-tcp'
namespaces.JINGLE_RAWUDP = 'http://www.xmpp.org/extensions/xep-0177.html#ns'
namespaces.JINGLE_FT = 'http://www.xmpp.org/extensions/xep-xxxx.html#ns'

def gen_jingle_action_xpath(act):
    return "/iq/*[@xmlns='%s'][action='%s']" % (namespaces.JINGLE, act)

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
    def initJingle(self, entity):
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
        self._entity.disco.addFeature(namespaces.JINGLE_FT)
    
    def onSessionInitiate(self, iq):
        "Called when someone wants to initiate a jingle session with us"
        pass
    def onSessionAccept(self, iq):
        "Called when someone accepts our session invitation"
        pass
    def onSessionTerminate(self, iq):
        "Called when someone wants to terminate our session"
        pass
    
    def onContentAccept(self, iq):
        "Called when someone accepts content"
        pass
    def onContentAdd(self, iq):
        "Called when someone wants to add a content stream"
        pass
    def onContentModify(self, iq):
        "Called when someone wants to modify a content stream"
        pass
    def onContentRemove(self, iq):
        "Called when someone wants to remove a content stream"
        pass
    
