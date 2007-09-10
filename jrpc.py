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
    def __init__(self, entity, rpc_jid):
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
