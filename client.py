from twisted.words.protocols.jabber import client
from twisted.words.protocols.jabber import xmlstream as jxml
from twisted.words.xish.xpath import XPathQuery
from twisted.words.xish import domish
from twisted.python import log
from utils import presenceStanza, messageStanza, updateAttribsFromDict, FEATURE_NOT_IMPLEMENTED
from twisted.internet import interfaces

import xpaths, namespaces

class Disco:
    def __init__(self, entity, category, type):
        self._features = [namespaces.DISCO_INFO]
        self.identities = [{'category': category, 'type': type}]
        self.nodes = {}
        self._entity = entity
        #self._entity.register(self)
        #self._entity.addIqHook(DISCO_INFO, self.discoInfo)
        self._entity.iq_get_hooks.addXPathHook(xpaths.DISCO_INFO, self.discoInfo)
        self._entity.iq_get_hooks.addXPathHook(xpaths.DISCO_ITEMS, self.discoItems)

    #    def xaddObservers(self, xmlstream):
    #        self._xmlstream = xmlstream
    #        xmlstream.addObserver(xpaths.DISCO_INFO, self.discoInfo)
    #        xmlstream.addObserver(xpaths.DISCO_ITEMS, self.discoItems)
    #        #for node in self.nodes:
    #        #    self.nodes[node].addObservers(xmlstream)

    def discoInfo(self, iq):
        node = iq.query.getAttribute('node')
        if node:
            if node in self.nodes: # we know about this node
                return self.nodes[node].discoInfo(self, iq)
        log.msg("discoInfo")
        #log.msg(iq.toXml())
        iq.swapAttributeValues('from', 'to')
        iq['type'] = 'result'
        iq.children = []
        q = iq.addElement("query", namespaces.DISCO_INFO)
        for i in self.identities:
            queryIdent = q.addElement("identity", None, "")
            queryIdent['category'] = i['category']
            queryIdent['type'] = i['type']
            if 'name' in i:
                queryIdent['name'] = i['name']
        for f in self._features:
            queryFeat = q.addElement("feature", None, "")
            queryFeat['var'] = f
        #log.msg("sending:"+iq.toXml())
        self._entity._xmlstream.send(iq)

    def iteritems(self):
        for i in self.features:
            yield i

    def discoItems(self, iq):
        log.msg("discoItems")
        node = iq.query.getAttribute('node')
        if node:
            if node in self.nodes:
                iq.swapAttributeValues('from', 'to')
                iq['type'] = 'result'

                for i in self.nodes[node].iteritems_for_jid(iq['from']):
                    thisItem = iq.query.addElement("item")
                    thisItem['jid'] = self._entity._jid.full()
                    updateAttribsFromDict(thisItem, i)
                self._entity._xmlstream.send(iq)
        else:
            iq.swapAttributeValues('from', 'to')
            iq['type'] = 'error'
            e = iq.query.addElement("error")
            e['type'] = 'cancel'
            e.children = [FEATURE_NOT_IMPLEMENTED]
            self._entity._xmlstream.send(iq)

    def addNode(self, name, obj):
        self.nodes[name] = obj

    def addFeature(self, name, obj):
        self._features.append(name)

class FileSaver:
    "Data consumer which writes data to a file"
    def __init__(self, filename, size, local_filename):
        self.file = None
        self.filename = filename
        self.local_filename = local_filename
        self.size = size
        self.written = 0
    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.file = open(self.local_filename, 'w')
    def unregisterProducer(self):
        self.producer = None
        self.close()
    def write(self, data):
        if self.file:
            self.file.write(data)
            self.written += len(data)
            if self.written >= self.size:
                self.close()
                self.onCompleted()
    def error(self):
        self.close()
    def close(self):
        if self.file:
            self.file.close()
            self.file = None
            self.onCompleted(self)
    def onCompleted(self): pass

class IdleMixin:
    def setIdleTime(self, idle_seconds=10, away_seconds=30):
        self.idle_seconds = idle_seconds
        self.away_seconds = away_seconds
        self.antiIdleActivity()
    def antiIdleActivity(self):
        from twisted.internet import reactor
        if hasattr(self, "waitIdle") and \
            self.waitIdle.active():
                self.waitIdle.reset(self.idle_seconds)
        else:
            self.waitIdle = reactor.callLater(self.idle_seconds, self.away)
            #, self.away)
        if hasattr(self, "waitAway") and \
            self.waitAway.active():
                self.waitAway.reset(self.away_seconds)
        else:
            self.waitAway = reactor.callLater(self.away_seconds, self.extended_away)
        self.showText = None # have to set it like this..
        self.setStatus() # send presence stanza
    def away(self):
        self.setStatus(showText='away')
    def extended_away(self):
        self.setStatus(showText='xa')

class EventHooks:
    def __init__(self):
        self.xpath_hooks = {} # hooks for xpath queries
        self.hooks = [] # callbacks for *any* event
    def addXPathHook(self, xpath_query, callback):
        self.xpath_hooks[(xpath_query, callback)] = XPathQuery(xpath_query), callback
    def addHook(self, callback):
        if callback not in self.hooks:
            self.hooks.append(callback)
    def removeXPathHook(self, xpath_query, callback):
        if (xpath_query, callback) in self.xpath_hooks:
            del self.xpath_hooks[(xpath_query, callback)]
    def removeHook(self, callback):
        if callback in self.hooks:
            self.hooks.remove(callback)
    def notifyEvent(self, xml_fragment, xml_report):
        "Calls the callbacks which match"
        for c in self.hooks:
            # firstly, the 'wildcard' hooks
            c(xml_report)
        found_match = False
        for key, value in self.xpath_hooks.iteritems():
            if value[0].matches(xml_fragment):
                found_match = True
                value[1](xml_report)
        return found_match

class BasicJabberClient:
    def __init__(self, myJID, myPassword, identity_type):
        self._xmlstream = None
        self.iq_get_hooks = EventHooks()
        self.iq_set_hooks = EventHooks()
        self.message_hooks = EventHooks()
        
        self.observers = []
        self.disco = Disco(self, 'client', identity_type)
        self._jid = myJID
        self._password = myPassword
        self._factory = client.basicClientFactory(self._jid, self._password)
        self._factory.addBootstrap(jxml.STREAM_AUTHD_EVENT, self.streamAuthenticated)
        self._factory.addBootstrap(jxml.STREAM_CONNECTED_EVENT, self.streamConnected)
        self._factory.addBootstrap(jxml.STREAM_END_EVENT, self.streamEnded)
        self._factory.addBootstrap(jxml.STREAM_ERROR_EVENT, self.streamError)
        self._factory.addBootstrap(jxml.STREAM_START_EVENT, self.streamStarted)
        if hasattr(jxml, "TLS_FAILED_EVENT"):
            self._factory.addBootstrap(jxml.TLS_FAILED_EVENT, self.tlsFailed)
        self.showText = None
        self.statusText = ''
        self.priority = 0

    #def register(self, observer):
    #    self.observers.append(observer)

    #def unregister(self, observer):
    #    self.observers.remove(observer)

    def streamAuthenticated(self, xmlstream):
        self._xmlstream = xmlstream
        #for o in self.observers:
        #    o.addObservers(self._xmlstream)
        self._xmlstream.addObserver('/message', self.gotMessage)
        self._xmlstream.addObserver("/iq[@type='error']", self.onIqError)
        
        # observers for iq get/set - other classes should use hook_iq_get/hook_iq_set
        self._xmlstream.addObserver("/iq[@type='get']", self.onIqGet)
        self._xmlstream.addObserver("/iq[@type='set']", self.onIqSet)
        
        #self._xmlstream.addObserver(xpaths.PRESENCE_SUBSCRIBE, self.onSubscribe)
        #self._xmlstream.addObserver(xpaths.PRESENCE_UNSUBSCRIBE, self.onUnSubscribe)
        #self._xmlstream.addObserver(STREAM_INITIATE_FILETRANSFER_START, self.onFileTransfer)
        self.setStatus(statusText="Online")


    def onIqGet(self, iq):
        noMatch = True
        log.msg("iq_get")
        if iq.firstChildElement():
            elem = iq.firstChildElement()
            noMatch = not self.iq_get_hooks.notifyEvent(elem, iq)
        if noMatch:
            log.msg("Unsupported IQ.GET: " + iq.toXml())
            elem = iq.firstChildElement() or iq
            iq.swapAttributeValues('from', 'to')
            iq['type'] = 'error'
            e = elem.addElement("error")
            e['type'] = 'cancel'
            e.children = [FEATURE_NOT_IMPLEMENTED]
            self._xmlstream.send(iq)

    def onIqSet(self, iq):
        noMatch = True
        if iq.firstChildElement():
            elem = iq.firstChildElement()
            noMatch = not self.iq_set_hooks.notifyEvent(elem, iq)
        if noMatch:
            log.msg("Unsupported IQ.SET: " + iq.toXml())
            elem = iq.firstChildElement() or iq
            iq.swapAttributeValues('from', 'to')
            iq['type'] = 'error'
            e = elem.addElement("error")
            e['type'] = 'cancel'
            e.children = [FEATURE_NOT_IMPLEMENTED]
            self._xmlstream.send(iq)
        
    def streamConnected(self, xmlstream): pass
    def streamEnded(self, xmlstream): pass
    def streamError(self, xmlstream): pass
    def streamStarted(self, xmlstream): pass
    def tlsFailed(self, xmlstream): pass

    def onIqError(self, iq):
        log.err("HERE'S AN ERROR: " + iq.toXml())
        pass

    def setStatus(self, statusText=None, showText=None, priority=None):
        if statusText:
            self.statusText = statusText
        if showText:
            self.showText = showText
        if priority:
            self.priority = priority
        if self._xmlstream == None:
            return
        p = presenceStanza(status=self.statusText, show=self.showText, priority=self.priority)
        self._xmlstream.send(p)

    def gotMessage(self, msg):
        "Called when we've received a message.. check our hooks list and call anyone interested"
        self.message_hooks.notifyEvent(msg, msg)

    def sendMessage(self, to=None, body=None):
        self._xmlstream.send(messageStanza(to, body))


class RosterJabberClient(BasicJabberClient):
    def __init__(self, myJID, myPassword, identity_type):
        BasicJabberClient.__init__(self, myJID, myPassword, identity_type)
        self.onlineContacts = []
        
    def streamAuthenticated(self, xmlstream):
        BasicJabberClient.streamAuthenticated(self, xmlstream)

        self.presence_hooks = EventHooks()
        self._xmlstream.addObserver('/presence', self.onPresence)
        self.iq_set_hooks.addXPathHook("/*[@xmlns='jabber:iq:roster']", self.onRosterIq)
        self.presence_hooks.addXPathHook(xpaths.PRESENCE_SUBSCRIBE, self.onSubscribe)
        self.presence_hooks.addXPathHook(xpaths.PRESENCE_UNSUBSCRIBE, self.onUnSubscribe)
        # request roster
        iq = client.IQ(self._xmlstream, type='get')
        iq.addElement("query", "jabber:iq:roster")
        iq.addCallback(self.onReceiveRoster)
        iq.send()

    def onReceiveRoster(self, iq):
        log.msg("onReceiveRoster")
        pass

    def onRosterIq(self, iq):
        log.msg("onRosterIq")
        pass
    
    def onSubscribe(self, presence): pass
    def onUnSubscribe(self, presence):
        self.contactUnsubscribed(presence)
    
    def allowSubscribe(self, presence):
        "Call this from onSubscribe to allow a contact to subscribe to our presence"
        log.msg("Allowing %s to subscribe to our presence" % presence['from'])
        presence['to'] = presence['from']
        presence['type'] = 'subscribed'
        self._xmlstream.send(presence)

        # automatically ask for subscription
        log.msg("Requesting authorisation from %s" % presence['to'])
        new_pre = domish.Element(("jabber:client", "presence"))
        new_pre['to'] = presence['to']
        new_pre['type'] = 'subscribe'
        self._xmlstream.send(new_pre)

    def contactUnsubscribed(self, presence):
        "Call this from OnUnSubscribe to acknowledge and remove contact from our roster"
        log.msg("%s removed us from their roster - doing likewise" % presence['from'])
        presence.swapAttributeValues('to', 'from')
        presence['type'] = 'unsubscribed'
        self._xmlstream.send(presence)

        # and remove jid from roster
        iq = client.IQ(self._xmlstream, type="set")
        query = iq.addElement(("jabber:iq:roster", "query"))
        query.addElement("item")
        query.item['jid'] = presence['to']
        query.item['subscription'] = 'remove'
        iq.send()
        
    def onPresence(self, p):
        if p.getAttribute('type') == 'unavailable':
            if p['from'] in self.onlineContacts:
                self.onlineContacts.remove(p['from'])
            self.onContactUnavailable(p)
        else:
            if p['from'] not in self.onlineContacts:
                self.onlineContacts.append(p['from'])
                self.onContactAvailable(p)
            else:
                self.onContactStatusChange(p['from'], p)
        self.presence_hooks.notifyEvent(p, p)

    def onContactUnavailable(self, p): pass
    def onContactAvailable(self, p): pass
    def onContactStatusChange(self, jid, p): pass
