from twisted.python import log
from twisted.words.xish import domish
from twisted.internet import defer
import namespaces, xpaths
import types

namespaces.JRPC = 'jabber:iq:rpc'
xpaths.JRPC_IQ = "//iq/*[@xmlns='%s']" % namespaces.JRPC

from xmlrpclib import Marshaller

def unmarshall(e):
    if e.name in ['i4', 'int']:
        return int(str(e))
    elif e.name == 'string':
        return str(e)
    elif e.name == 'double':
        return float(str(e))
    elif e.name == 'base64':
        return ''
    elif e.name == 'boolean':
        if str(e) == '1':
            return True
        return False
    elif e.name == 'dateTime.iso8601':
        return None
    elif e.name == 'array':
        return []
    elif e.name == 'struct':
        return {}

def encode_params(parms, args):
    m = Marshaller()
    parms.addRawXml(m.dumps(args))

class JRPCServer:
    """
    This class exports functions via jabber rpc.

    To use:
    class MyEntity(BasicJabberClient):
        def __init__(self, ...):
            BasicJabberClient.__init__(self, ...)
            self.jrpc = JRPCServer(self)
        def rpc_test(self, param1, param2):
            return "it worked"
        def rpc_testDefer(self, param):
            d = defer.Deferred()
            def f():
                d.callback("it worked")
            reactor.callLater(10, f)
            return d

    alternatively, stuff callables into <JRPCServer instance>.methods
    """
    def __init__(self, entity):
        self.methods = {}
        self._entity = entity
        self._entity.disco.identities.append({'category': 'automation', 'type': 'rpc'})
        self._entity.disco.addFeature(namespaces.JRPC)
        self._entity.iq_set_hooks.addObserver(xpaths.JRPC_IQ, self.rpcMethod)

    def rpcMethod(self, i):
        call = i.query.methodCall
        methodName = str(call.methodName)
        params = call.params
        args = []
        for p in params.elements():
            args.append(unmarshall(p.value.firstChildElement()))

        m = None
        if methodName in self.methods:
            m = self.methods(methodName)
        else:
            m = getattr(self._entity, 'rpc_%s' % methodName)

        response_iq = self._entity.getIQ(type="result")
        response_iq['id'] = i['id']
        query = response_iq.addElement((namespaces.JRPC, 'query'))
        response = query.addElement((None, 'methodResponse'))

        def respond(value):
            encode_params(response, value)
            response_iq.send(i['from'])
        defer.maybeDeferred(m, args).addCallback(respond)

class JRPCServerProxy:
    """
    This class works much like python's own xmlrpclib.ServerProxy.

    To use:
    s = JRPCServerProxy(myEntity, 'rpcserver@jabber.server')
    def callback(value):
        print value
    s.testMethod(1,2,3).addCallback(callback)
    """
    def __init__(self, entity, rpc_jid):
        """
        entity - the jabber entity with which this instance is to be associated (uses entity's xmlstream to
        send IQs)
        rpc_jid - the JID of the JRPC server
        """
        self._entity = entity
        self.rpcJid = rpc_jid
    def __getattr__(self, key):
        "Returns a function object configured to remote-call"
        def f(*args):
            myIq = self._entity.getIQ()
            myIq.addElement((namespaces.JRPC, 'query'))
            methodCall = myIq.query.addElement((None, 'methodCall'))
            methodCall.addElement((None, 'methodName'), content=key)

            encode_params(methodCall, args)

            d = defer.Deferred()
            myIq.send(self.rpcJid)
            def r(i):
                params = i.query.methodResponse.params
                args = []
                for p in params.elements():
                    args.append(unmarshall(p.value.firstChildElement()))
                d.callback(args)

            myIq.addCallback(r)
            return d
        return f
