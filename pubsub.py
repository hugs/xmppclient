import xpaths, namespaces
from twisted.words.xish import domish
from twisted.words.protocols.jabber.client import IQ
from twisted.words.protocols.jabber.jid import internJID, JID
from twisted.python import log

namespaces.pubsub = 'http://jabber.org/protocol/pubsub'
namespaces.pubsub_node_config = namespaces.pubsub + '#node_config'
namespaces.pubsub_event = namespaces.pubsub + '#event'

xpaths.PUBSUB_MESSAGE_EVENT = "//event[@xmlns='%s']" % (namespaces.pubsub + '#event')

DEFAULT_ACCESS = -1
PUBLIC_ACCESS = 0
PRESENCE_ACCESS = 1

def pubsubIQ(xmlstream, type="set"):
    result = IQ(xmlstream, type=type)
    result.addElement((namespaces.pubsub, 'pubsub'))
    return result

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

class PubSub:
    def __init__(self, entity, pubsub_jid, oldstyle=True):
        self._entity = entity
        self.PubSubItems = {}
        self.oldstyle = oldstyle
        self._pubsub_jid = pubsub_jid
        def f(e):
            self._entity._xmlstream.addObserver("/message/event[@xmlns='%s']" % namespaces.pubsub_event, self.gotMessage)
        self._entity.addObserver('//event/CONNECTION_AUTHENTICATED', f)

        self._entity.disco.addNode('http://jabber.org/protocol/pubsub', self)
        self._entity.disco.addFeature('http://jabber.org/protocol/pubsub', self)

    def gotMessage(self, msg):
        log.msg(msg.firstChildElement().toXml())

    def get(self, jid, node, item_id):
        iq = pubsubIQ(self._entity._xmlstream)
        items = iq.pubsub.addElement("items")
        items['node'] = node
        item = items.addElement('item')
        item['id'] = item_id
        iq.addCallback(self.getCallback)
        iq.send(jid)

    def getCallback(self, iq):
        if iq['type'] == 'result':
            log.msg(xpath.queryForNodes('/pubsub/items/item/*', iq))
            for e1 in xpath.queryForNodes('/pubsub/items/item/'):
                for e2 in xpath.queryForNodes('/pubsub/items/item/*', iq):
                    self.PubSubItems[e1['id']] = e2
        else:
            pass

    def unsubscribe(self, jid, node):
        iq = pubsubIQ(self._entity._xmlstream)
        unsub = iq.pubsub.addElement(('', 'unsubscribe'))
        unsub['node'] = node
        unsub['jid'] = self._jid.userhost();
        iq.addCallback(self.unsubscribeCallback)
        iq.send(jid)

    def unsubscribeCallback(self, x):
        log.msg(x.toXml())
        if x['type'] == 'result':
            log.msg("unsubscribe ok")
        else:
            pass

    def subscribe(self, node):
        iq = pubsubIQ(self._entity._xmlstream)
        subscr = iq.pubsub.addElement('subscribe')
        subscr['node'] = node
        subscr['jid'] = self._entity._jid.userhost()
        iq.addCallback(self.subscribeCallback)
        iq.send(self._pubsub_jid)
        log.msg("BYE")

    def subscribeCallback(self, x):
        if x['type'] == 'result':
            log.msg("subscribe ok")
        else:
            log.msg("subscribe not ok")

    def getSubscriptions(self, jid):
        iq = pubsubIQ(self._entity._xmlstream, 'get')
        iq.pubsub.addElement("subscriptions")
        iq.addCallback(self.getSubscriptionsCallback)
        iq.send(jid.userhost())

    def getSubscriptionsCallback(self, x):
        log.msg("GetSubscriptionsCallback")
        if x['type'] == 'result':
            self.subscriptions = []
            for m in x.children:
                if m.name != 'pubsub':
                    continue
                for n in m.children:
                    if n.name != 'subscriptions':
                        continue
                    for sub_node in n.children:
                        self.subscriptions.append(PubSubSubscription(sub_node))
        else:
            pass

    def createNode(self, node=None, callback=None):
        iq = pubsubIQ(self._entity._xmlstream)
        iq.pubsub.addElement('create')
        if node <> None:
            iq.pubsub.create['node'] = node
        if not self.oldstyle:
            iq.pubsub.addElement('configure')
        if callback:
            iq.addCallback(callback)
        iq.addCallback(self.createNodeCallback)
        iq.send(self._pubsub_jid)

    def createNodeCallback(self, x):
        if x['type'] == 'result':
            log.msg("created node"+x.toXml())
        else:
            if x.error.firstChildElement().name == 'conflict':
                log.msg("node already exists")

    def deleteNode(self, node):
        iq = pubsubIQ(self._entity._xmlstream)
        iq.pubsub.addElement('delete')
        iq.pubsub.delete['node'] = node
        iq.addCallback(self.deleteNodeCallback)
        iq.send(self._pubsub_jid)

    def deleteNodeCallback(self, x):
        if x['type'] == 'result':
            log.msg("node deleted")
        else:
            pass

    def publish(self, node, item, access=DEFAULT_ACCESS):
        iq = pubsubIQ(self._entity._xmlstream)
        publish = iq.pubsub.addElement('publish')
        publish['node'] = node
        if item:
            xmlitem = publish.addElement('item')
            xmlitem['id'] = item['id']
            xmlitem.children = item.children
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

        iq.addCallback(self.publishCallback)
        log.msg(iq.toXml())
        iq.send(self._pubsub_jid)
    
    def publishCallback(self, x):
        if x['type'] == 'result':
            log.msg("PublishCallback ok")
            log.msg(x.toXml())
        else:
            log.msg("problem publishing")

    def retract(self, node, item_id):
        iq = pubsubIQ(self._entity._xmlstream)
        retract = iq.pubsub.addElement('retract')
        retract['node'] = node
        retract['notify'] = '1'
        item = retract.addElement('item')
        item['id'] = item_id
        iq.addCallback(self.retractCallback)
        iq.send(self._pubsub_jid)

    def retractCallback(self, x):
        if x['type'] == 'result':
            pass
            print "retaction ok"
        else:
            pass

