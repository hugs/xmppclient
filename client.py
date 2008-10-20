from twisted.words.protocols.jabber import client, jid
from twisted.words.protocols.jabber import xmlstream as jxml
from twisted.words.xish.xpath import XPathQuery
from twisted.words.xish import domish, utility
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
        self._entity.iq_get_hooks.addObserver(xpaths.DISCO_INFO, self.discoInfo)
        self._entity.iq_get_hooks.addObserver(xpaths.DISCO_ITEMS, self.discoItems)

    def discoInfo(self, iq):
        node = iq.query.getAttribute('node')
        if node:
            if node in self.nodes: # we know about this node
                return self.nodes[node].discoInfo(self, iq)
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
        self._entity._xmlstream.send(iq)

    def iteritems(self):
        for i in self.features:
            yield i

    def discoItems(self, iq):
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

    def addFeature(self, name, obj=None):
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

# the following class is useful for when you're testing sending/receiving IQs
# to yourself over the same xmlstream..
# twisted's own IQ class fires callbacks as the inital IQ gets sent, and clears the callbacklist
# so that the result IQ response causes an error
class MyIQ(client.IQ):
    def send(self, to=None):
        if to != None:
            self['to'] = to
        if self['type'] in ('get', 'set'):
            #self._xmlstream.addOnetimeObserver("/iq[@id='%s'][@type!='%s']" % (self['id'], self['type']), self._resultEvent)
            self._xmlstream.addOnetimeObserver("/iq[@id='%s']" % self['id'], self._resultEvent)
        self._xmlstream.send(self)
    def _resultEvent(self, iq):
        self.callbacks.callback(iq)

class BasicJabberClient(utility.EventDispatcher):
    def __init__(self, myJID, myPassword, identity_type):
        utility.EventDispatcher.__init__(self)
        self._xmlstream = None
        self.iq_get_hooks = utility.EventDispatcher()
        self.iq_set_hooks = utility.EventDispatcher()
        self.message_hooks = utility.EventDispatcher()
        
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
    
    def _rawDataIn(self, data):
        self.dispatch(data, '//event/RAW_DATA_IN')
        
    def _rawDataOut(self, data):
        self.dispatch(data, '//event/RAW_DATA_OUT')

    def streamAuthenticated(self, xmlstream):
        log.msg("connection authenticated")
        self._xmlstream = xmlstream
        self._xmlstream.rawDataInFn = self._rawDataIn
        self._xmlstream.rawDataOutFn = self._rawDataOut
        self._xmlstream.addObserver('/message', self.onMessage)
        self._xmlstream.addObserver("/iq[@type='error']", self.onIqError)
        self._xmlstream.addObserver("/iq[@type='get']", self.onIqGet)
        self._xmlstream.addObserver("/iq[@type='set']", self.onIqSet)

        #self.setStatus(statusText="Online")
        self.dispatch('ok', '//event/CONNECTION_AUTHENTICATED')

    def onIqGet(self, iq):
        noMatch = True
        if iq.firstChildElement():
            elem = iq.firstChildElement()
            noMatch = not self.iq_get_hooks.dispatch( iq )
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
            noMatch = not self.iq_set_hooks.dispatch( iq )
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
        log.err("ERROR: " + iq.toXml())
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

    def onMessage(self, msg):
        "Called when we've received a message.. check our hooks list and call anyone interested"
        # alert callbacks waiting for any kind of message
        self.message_hooks.dispatch(msg, '//event/RECEIVE')
        # alert callbacks with xpath selectors
        self.message_hooks.dispatch( msg )

    def sendMessage(self, to=None, body=None):
        self._xmlstream.send(messageStanza(to, body))
    def getIQ(self, type="set"):
        return MyIQ(self._xmlstream, type)

class RosterJabberClient(BasicJabberClient):
    def __init__(self, myJID, myPassword, identity_type):
        BasicJabberClient.__init__(self, myJID, myPassword, identity_type)
        self.onlineContacts = {}
        self.rosterContacts = []
        
    def streamAuthenticated(self, xmlstream):
        BasicJabberClient.streamAuthenticated(self, xmlstream)
        
        self.presence_hooks = utility.EventDispatcher()
        self._xmlstream.addObserver('/presence', self.onPresence)
        self.iq_set_hooks.addObserver("/*[@xmlns='jabber:iq:roster']", self.onRosterIq)
        self.presence_hooks.addObserver(xpaths.PRESENCE_SUBSCRIBE, self.onSubscribe)
        self.presence_hooks.addObserver(xpaths.PRESENCE_UNSUBSCRIBE, self.onUnSubscribe)

        self.setStatus(statusText="Online")
        # request roster
        iq = client.IQ(self._xmlstream, type='get')
        iq.addElement("query", "jabber:iq:roster")
        iq.addCallback(self.onReceiveRoster)
        iq.send()

    def onReceiveRoster(self, iq):
        # JRH - Sauce Labs - Bug fix - rosters were not being reset properly.
        # If a new copy of the entire roster was resent by the server,
        # the list should be reset to zero before  adding to it.
        self.rosterContacts = []
        # JRH - end

        items = iq.children[0].children
        for i in items:
            self.rosterContacts.append(i['jid'])

    def onRosterIq(self, iq):
        pass
    
    def onSubscribe(self, presence):
        """Called when someone tries to subscribe to our presence (adds us to their roster)
        Override this, and call self.allowSubscribe(presence) to permit this"""
        pass
    def onUnSubscribe(self, presence):
        """Called when someone removes us from their contact list. Default action is to remove them from ours"""
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
        self.rosterContacts.append(presence['from']) # should probably wait til we receive confirmation

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
        self.rosterContacts.remove(presence['to'])
        if presence['to'] in self.onlineContacts:
            del self.onlineContacts[presence['to']]
        
    def onPresence(self, p):
        if p.getAttribute('type') == 'unavailable':
            self.onContactUnavailable(p)
        else:
            self.onContactAvailable(p)
            if p.show:
                self.dispatch((p['from'], p.show.__str__()), '//event/CONTACT_SHOW')
            else:
                self.dispatch((p['from'], 'online'), '//event/CONTACT_SHOW')
        self.presence_hooks.dispatch(p)

    def onContactUnavailable(self,p):
        j = jid.internJID(p['from'])
        c = self.onlineContacts.get(j.userhost(), [])
        if j.resource in c:
            c.remove(j.resource)
            self.dispatch(j, '//event/RESOURCE_UNAVAILABLE')
        if c == []:
            if j.userhost() in self.onlineContacts:
                del self.onlineContacts[j.userhost()]
                self.dispatch(j.userhost(), '//event/CONTACT_UNAVAILABLE')
        else:
            self.onlineContacts[j.userhost()] = c
    def onContactAvailable(self, p):
        j = jid.internJID(p['from'])
        c = self.onlineContacts.get(j.userhost(), [])
        # JRH - Sauce Labs - Bug fix - The list of xmpp resources were
        # growing in size on every update for the contact. Now, we only 
        # add to the list if it's not already in the list.
        if j.resource not in c:
            c.append(j.resource)
        # JRH - end

        self.onlineContacts[j.userhost()] = c
        if len(c) == 1:
            self.dispatch(j.userhost(), '//event/CONTACT_AVAILABLE')
        self.dispatch(j, '//event/RESOURCE_AVAILABLE')
    def onContactStatusChange(self, jid, p):
        self.dispatch((jid, p), '//event/CONTACT_STATUS_CHANGE')
        pass
