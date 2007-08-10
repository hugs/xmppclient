from twisted.words.xish import domish

FEATURE_NOT_IMPLEMENTED = domish.Element(('urn:ietf:params:xml:ns:xmpp-stanzas', "feature-not-implemented"))
def presenceStanza(status=None, priority=None, show=None):
    pre = domish.Element(("jabber:client", "presence"))
    if status:
        pre.addElement("status", None, status)
    if priority:
        pre.addElement("priority", None, str(priority))
    if show:
        pre.addElement("show", None, show)
    return pre

def messageStanza(to, body, type='chat'):
    msg = domish.Element(("jabber:client", "message"))
    msg['type'] = type
    msg['to'] = to
    msg.addElement("body", None, body)
    return msg

def updateAttribsFromDict(element, attribs):
    for k,v in attribs.iteritems():
        element[k] = v

