import xpaths, namespaces
from twisted.words.xish import domish, xpath, utility
from twisted.words.protocols.jabber.client import IQ
from twisted.words.protocols.jabber.jid import internJID, JID
from twisted.python import log
from twisted.internet import defer

namespaces.pubsub = 'http://jabber.org/protocol/pubsub'
namespaces.pubsub_node_config = namespaces.pubsub + '#node_config'
namespaces.pubsub_event = namespaces.pubsub + '#event'

xpaths.PUBSUB_MESSAGE_EVENT = "/message/*[@xmlns='%s']" % (namespaces.pubsub_event)

DEFAULT_ACCESS = -1
PUBLIC_ACCESS = 0
PRESENCE_ACCESS = 1

class PubSubItem(domish.Element):
    def __init__(self):
        domish.Element.__init__(self, ('', 'item'))
        self.addUniqueId()
        entry = self.addElement('entry')
        title = entry.addElement('title')
        summary = entry.addElement('summary')
        link = entry.addElement('link')

        log.msg(self.toXml())

class UserLocation(domish.Element):
    def __init__(self, alt=None, area=None, bearing=None, building=None, country=None, datum=None, description=None, error=None, floor=None, lat=None, locality=None, lon=None, postalcode=None, region=None, room=None, street=None, text=None, timestamp=None, uri=None):
        domish.Element.__init__(self, ('http://jabber.org/protocol/geoloc', 'geoloc'))
        self.addUniqueId()
        if alt: self.addElement('alt', content=alt)
        if area: self.addElement('area', content=area)
        if bearing: self.addElement('bearing', content=bearing)
        if building: self.addElement('building', content=building)
        if country: self.addElement('country', content=country)
        if datum: self.addElement('datum', content=datum)
        if description: self.addElement('description', content=description)
        if error: self.addElement('error', content=error)
        if floor: self.addElement('floor', content=floor)
        if lat: self.addElement('lat', content=lat)
        if locality: self.addElement('locality', content=locality)
        if lon: self.addElement('lon', content=lon)
        if postalcode: self.addElement('postalcode', content=postalcode)
        if region: self.addElement('region', content=region)
        if room: self.addElement('room', content=room)
        if street: self.addElement('street', content=street)
        if text: self.addElement('text', content=text)
        if timestamp: self.addElement('timestamp', content=timestamp)
        if uri: self.addElement('uri', content=uri)

class UserTune(domish.Element):
    def __init__(self, artist=None, length=None, source=None, title=None, track=None, uri=None):
        domish.Element.__init__(self, ('http://jabber.org/protocol/tune', 'tune'))
        self.addUniqueId()
        if artist: self.addElement('artist', content=artist)
        if length: self.addElement('length', content=length)
        if source: self.addElement('source', content=source)
        if title: self.addElement('title', content=title)
        if track: self.addElement('track', content=track)
        if uri: self.addElement('uri', content=uri)

class UserActivity(domish.Element):
    def __init__(self, activity, specific_activity, text=None):
        domish.Element.__init__(self, ('http://jabber.org/protocol/activity', 'activity'))
        self.addUniqueId()
        a = self.addElement('activity')
        a2 = a.addElement(activity)
        if specific_activity: a2.addElement(specific_activity)
        if text:
            a.addElement('text', content=text)

class UserMood(domish.Element):
    def __init__(self, mood, text=None):
        domish.Element.__init__(self, ('http://jabber.org/protocol/mood', 'mood'))
        self.addUniqueId()
        a2 = self.addElement(mood)
        if text:
            self.addElement('text', content=text)

class PubSubReplicator:
    """
    A class which publishes copies of subscribed nodes/items under its own hierarchy.
    Essentially a pubsub load distributor
    """
    def __init__(self, entity, local_pubsub_jid, filters=None):
        self._entity = entity
        self.pubsub = PubSub(entity, local_pubsub_jid)
        self.remote_pubsubs = {}
        self.node_maps = {}
        self.filters = filters
        # ensure we have a node path to publish to
        log.msg("trying to create immediate node")
        self.pubsub.createNode().addCallback(self.initialNodeCreated)

    def initialNodeCreated(self, node):
        log.msg("created node %s ok" % node)
        self.pubsub.deleteNode(node)
        if self.filters:
            for key, value in self.filters.iteritems():
                pubsub_jid, remote_node = key

                if pubsub_jid not in self.remote_pubsubs:
                    self.remote_pubsubs[pubsub_jid] = PubSub(self._entity, pubsub_jid)
                def subscribe_callback(c):
                    log.msg("SUBSCRIBED %s" % c)

                #no_subscription = False
                #if (pubsub_jid, remote_node) not in self.node_maps:
                #    self.node_maps[(pubsub_jid, remote_node)] = []
                #    no_subscription = True
                #self.node_maps[(pubsub_jid, remote_node)].append(my_node)

                #if no_subscription:
                log.msg("attempting to subscribe to %s" % remote_node)
                self.remote_pubsubs[pubsub_jid].subscribe(remote_node, self.onItemPublished).addCallback(subscribe_callback)

                for local_node in value.keys():
                    log.msg("creating local node %s" % local_node)
                    def nodeCreated(n):
                        log.msg("node created %s" % n)
                    def nodeCreateError(e, n):
                        log.msg("node create error %s" % n)
                    self.pubsub.createNode(local_node).addCallbacks(nodeCreated, nodeCreateError, errbackArgs=(local_node,))
    
    def onItemPublished(self, (pubsub_jid, node, item)):
        if (pubsub_jid, node) in self.filters:
            test_filters = self.filters[(pubsub_jid, node)]
            for local_node, filter in test_filters.iteritems():
                filter_result = xpath.matches(filter, item)
                if filter_result:
                    log.msg("PubSubReplicator.onItemPublished %s:%s:%s" % (pubsub_jid, node, localnode))
                    self.pubsub.publish(local_node, item)

class PubSub:
    def _pubsubIQ(self, type="set"):
        iq = self._entity.getIQ(type)
        iq.addElement((namespaces.pubsub, 'pubsub'))
        return iq

    def __init__(self, entity, pubsub_jid, oldstyle=False):
        self._entity = entity
        self.PubSubItems = {}
        self.oldstyle = oldstyle
        self._pubsub_jid = pubsub_jid
        self.subscriptions = {}

        self._entity.disco.addNode('http://jabber.org/protocol/pubsub', self)
        self._entity.disco.addFeature('http://jabber.org/protocol/pubsub', self)

        self._entity.message_hooks.addObserver(xpaths.PUBSUB_MESSAGE_EVENT, self.gotMessage)

    def gotMessage(self, msg):
        thisnode = msg.event.items['node']
        for item in xpath.queryForNodes(xpaths.PUBSUB_MESSAGE_EVENT + "/items/item", msg):
            if thisnode in self.subscriptions:
                self.subscriptions[thisnode].dispatch((msg['from'], thisnode, item), '//event/RECEIVE')

    # don't think this is implemented in ejabberd..
    #def get(self, jid, node, item_id):
    #    iq = pubsubIQ(self._entity._xmlstream)
    #    items = iq.pubsub.addElement("items")
    #    items['node'] = node
    #    item = items.addElement('item')
    #    item['id'] = item_id
    #    iq.addCallback(self.getCallback)
    #    iq.send(jid)

    #def getCallback(self, iq):
    #    if iq['type'] == 'result':
    #        log.msg(xpath.queryForNodes('/pubsub/items/item/*', iq))
    #        for e1 in xpath.queryForNodes('/pubsub/items/item/'):
    #            for e2 in xpath.queryForNodes('/pubsub/items/item/*', iq):
    #                self.PubSubItems[e1['id']] = e2
    #    else:
    #        pass

    def unsubscribe(self, jid, node):
        iq = pubsubIQ(self._entity._xmlstream)
        unsub = iq.pubsub.addElement(('', 'unsubscribe'))
        unsub['node'] = node
        unsub['jid'] = self._jid.userhost();
        d = defer.Deferred()
        def usCallback(iq):
            if iq['type'] == 'result':
                #log.msg("unsubscribe ok from %s" % node)
                d.callback(iq)
            else:
                d.errback(iq)
        iq.addCallback(usCallback)
        iq.send(jid)
        return d

    def subscribe(self, node, callback, pubsub_jid=None):
        iq = self._pubsubIQ()
        subscr = iq.pubsub.addElement('subscribe')
        subscr['node'] = node
        subscr['jid'] = self._entity._jid.userhost()
        d = defer.Deferred()
        def sCallback(iq):
            if iq['type'] == 'result':
                log.msg("subscribed to %s" % node)
                if node not in self.subscriptions:
                    self.subscriptions[node] = utility.EventDispatcher()
                self.subscriptions[node].addObserver('//event/RECEIVE', callback)
                d.callback(node)
            else:
                d.errback(iq)
        iq.addCallback(sCallback)
        iq.send(pubsub_jid or self._pubsub_jid)
        return d

    # doesn't seem to be implemented in ejabberd..
    #def getSubscriptions(self, jid):
    #    iq = pubsubIQ(self._entity._xmlstream, 'get')
    #    iq.pubsub.addElement("subscriptions")
    #    iq.addCallback(self.getSubscriptionsCallback)
    #    iq.send(jid.userhost())

    #def getSubscriptionsCallback(self, x):
    #    log.msg("GetSubscriptionsCallback")
    #    if x['type'] == 'result':
    #        self.subscriptions = []
    #        for m in x.children:
    #            if m.name != 'pubsub':
    #                continue
    #            for n in m.children:
    #                if n.name != 'subscriptions':
    #                    continue
    #                for sub_node in n.children:
    #                    self.subscriptions.append(PubSubSubscription(sub_node))
    #    else:
    #        pass

    def createNode(self, node=None):
        iq = self._pubsubIQ()
        iq.pubsub.addElement('create')
        if node <> None:
            iq.pubsub.create['node'] = node
        if not self.oldstyle:
            iq.pubsub.addElement('configure')
        d = defer.Deferred()
        def cnCallback(iq):
            log.msg("cnCallback %s" % iq.toXml())
            if iq['type'] == 'result':
                log.msg("created node"+iq.toXml())
                d.callback(iq.pubsub.create['node']) # return node's id
            else:
                if iq.error.firstChildElement().name == 'conflict':
                    d.callback(iq.pubsub.create['node']) # return node's id
                else:
                    d.errback(iq)

        iq.addCallback(cnCallback)
        log.msg(iq.toXml())
        iq.send(self._pubsub_jid)
        return d

    def deleteNode(self, node):
        iq = self._pubsubIQ()
        iq.pubsub.addElement('delete')
        iq.pubsub.delete['node'] = node
        d = defer.Deferred()
        def dnCallback(iq):
            if iq['type'] == 'result':
                #log.msg("deleted node " + iq.toXml())
                d.callback(iq)
            else:
                d.errback(iq)
        iq.addCallback(dnCallback)
        iq.send(self._pubsub_jid)
        return d

    def publish(self, node, item, access=DEFAULT_ACCESS):
        iq = self._pubsubIQ()
        publish = iq.pubsub.addElement('publish')
        publish['node'] = node
        if item:
            publish.addChild(item)
        if (access <> DEFAULT_ACCESS):
            iq.pubsub.addElement("configure")
            iq.pubsub.configure.addElement(('jabber:x:data', "x")) 
            ft = q.pubsub.configure.x.addElement("field")
            ft.addElement("field")
            ft['var'] = 'FORM_TYPE'
            ft['type'] = 'hidden'
            ft.addElement('value', content=namespaces.pubsub_node_config)

            if access == PUBLIC_ACCESS:
                aml = iq.pubsub.configure.x.addElement('field', content='open')
            elif access == PRESENCE_ACCESS:
                aml = iq.pubsub.configure.x.addElement('field', content='presence')
            am1['var'] = "pubsub#access_mode1"
            am1_value = am1.addElement(('value', None))

        d = defer.Deferred()
        def pCallback(iq):
            if iq['type'] == 'result':
                d.callback(iq)
            else:
                d.errback(iq)
        iq.addCallback(pCallback)
        #log.msg(iq.toXml())
        iq.send(self._pubsub_jid)
        return d
    
    def retract(self, node, item_id):
        iq = pubsubIQ(self._entity._xmlstream)
        retract = iq.pubsub.addElement('retract')
        retract['node'] = node
        retract['notify'] = '1'
        item = retract.addElement('item')
        item['id'] = item_id
        d = defer.Deferred()
        def rCallback(iq):
            if iq['type'] == 'result':
                #log.msg("retracted item %s/%s" % (node, item_id))
                d.callback(iq)
            else:
                d.errback(iq)
        iq.addCallback(rCallback)
        iq.send(self._pubsub_jid)
        return d
