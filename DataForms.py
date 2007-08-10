from twisted.python import log
from twisted.words.xish import domish

class Field:
    fieldType = 'unknown'
    def postInit(self):
        pass
    def __init__(self, name, label=None, desc=None, value=None, required=False):
        self.name = name
        self.label = label
        self.value = value
        self.required = required
        self.desc = desc
        self.postInit()

    def getElement(self):
        f = domish.Element((None, "field"))
        f['type'] = self.fieldType
        if self.fieldType <> "fixed":
            f['var'] = self.name # necessary for everything except 'fixed' fields
        if self.label:
            f['label'] = self.label # MAY
        if self.desc:
            f.addElement("desc", None, desc)
        if self.required:
            f.addElement("required", None, '')
        if self.value:
            if isinstance(self.value, list): # multiple values..
                for v in self.value:
                    f.addElement("value", None, v)
            else:
                f.addElement("value", None, self.value)
        return f

class BooleanField(Field): fieldType = 'boolean'
class FixedField(Field): fieldType = 'fixed'
class HiddenField(Field): fieldType = 'hidden'
class JidMultiField(Field): fieldType = 'jid-multi'
class JidField(Field): fieldType = 'jid-multi'
class TextMultiField(Field): fieldType = 'text-multi'
class TextPrivateField(Field): fieldType = 'text-private'
class TextField(Field): fieldType = 'text-single'

class ListField(Field):
    # don't use this class.. just a superclass
    def postInit(self):
        self.options = []
    def addOptions(self, options):
        if isinstance(options, dict):
            for k,v in options.items():
                self.options.append(Option(k, v))
        elif isinstance(options, list):
            for i in options:
                self.options.append(Option(i))
    def getElement(self):
        f = Field.getElement(self)
        f.children.extend([o.getElement() for o in self.options])
        return f

class ListMultiField(ListField): fieldType = 'list-multi'
class ListSingleField(ListField): fieldType = 'list-single'

class Option:
    def __init__(self, value, label=None):
        self.value = value
        self.label = label
    def getElement(self):
        opt = domish.Element((None, "option"))
        if self.label:
            opt['label'] = self.label
        opt.addElement("value", None, self.value)
        return opt

class JabberForm:
    def __init__(self, title=None, instructions=None):
        self.title = title
        self.instructions = instructions
        self._fields = []
    
    def __getitem__(self, key):
        "Finds a field by name"
        for f in self._fields:
            if f.name == key:
                return f
        raise KeyError

    def __setitem__(self, key, value):
        "sets a field by name"
        f = self.__getitem__(key)
        f.value = value

    def add(self, f):
        self._fields.append(f)

    def getElement(self):
        x = domish.Element(("jabber:x:data", "x"), attribs={'type': 'result'})
        if self.title:
            x.addElement("title", None, self.title)
        if self.instructions:
            x.addElement("instructions", None, self.instructions)
        x.children.extend([f.getElement() for f in self._fields])
        return x

    def toDict(self):
        result = {}
        for f in self._fields:
            result[f.name] = f.value
        return result

class Wizard:
    def __init__(self):
        self.pages = []
        self.states = {}
        self._sessionid = 0
    def getNewSessionId(self):
        self._sessionid += 1
        return `self._sessionid`
    def addPage(self, form):
        self.pages.append(form)
    def _readFormDict(self, submitted):
        result = {}
        #log.msg("submitted form:"+submitted.toXml())
        for fieldElement in submitted.elements():
            if fieldElement.name == 'field':
                values = []
                for fieldValue in fieldElement.elements():
                    if fieldValue.name == 'value':
                        values.append(str(fieldValue))
                if values:
                    value = values[0]
                    if len(values) > 1:
                        value = values
                    result[fieldElement['var']] = value
        return result
    def processIq(self, xmlstream, iq):
        #log.msg("*** RECEIVED "+iq.toXml(), debug=1)
        sessionid = iq.command.getAttribute('sessionid')
        if sessionid == None:
            sessionid = self.getNewSessionId()
            self.states[sessionid] = {'page': 0, 'data': [], 'jid': iq['from']}
        if sessionid not in self.states:
            log.err("non-existant sessionid")
            # <xmpp:bad-request/> <cmd:bad-session/>
            # or
            # <xmpp:bad-request/> <cmd:session-expired/>
            return None
        myState = self.states[sessionid]
        stage = myState['page']
        #log.msg("*** SESSION:"+sessionid, debug=1)
        action = iq.command.getAttribute('action') or 'execute'
        #log.msg("*** ACTION:"+action, debug=1)
        validActions = []
        ok = False
        if action == 'execute': # start the whole thing off
            iq.command['sessionid'] = sessionid
            iq.swapAttributeValues('from', 'to')
            iq['type'] = 'result'
            iq.command['status'] = 'executing'
            form = self.pages[stage]
            self.onShowForm(form, stage, myState)
            eForm = form.getElement()
            iq.command.children = [eForm]
            if len(self.pages) > 1:
                validActions = ['next']
            else:
                validActions = ['complete']
            ok = True
        elif action == 'cancel': # you heard the man..
            if sessionid not in self.states:
                log.err("cancelling session.. but sessionid '%s' is not valid" % sessionid)
            else:
                del self.states[sessionid]
            iq.swapAttributeValues("from", "to")
            iq['type'] = 'result'
            iq.command['status'] = 'cancelled'
            iq.children = []
            ok = True
        elif action in ('next', 'complete'): # store results and show next form if there is one
            # store results..
            submittedDict = self._readFormDict(iq.command.x)
            #log.msg("Here're the submitted values:" + str(submittedDict))
            if len(myState['data']) <= stage:
                myState['data'].append(None)

            myState['data'][stage] = submittedDict
            # ..nothing here yet
            stage += 1
            myState['page'] = stage
            iq.command.children = []
            if stage < len(self.pages): # more forms to show
                form = self.pages[stage]
                self.onShowForm(form, stage, myState)
                eForm = form.getElement()
                iq.swapAttributeValues("from", "to")
                iq['type'] = 'result'
                iq.command['status'] = 'executing'
                iq.command.children = [eForm]
                if stage == len(self.pages)-1: # this is the last page..
                    validActions = ['prev', 'complete']
                else:
                    validActions = ['next', 'prev']
            else: # no more forms, wizard completed
                iq.swapAttributeValues("from", "to")
                iq['type'] = 'result'
                iq.command['status'] = 'completed'
                self.onComplete(xmlstream, iq['to'], myState['data'])
                # remove session
                del self.states[sessionid]
            ok = True
        elif action == 'prev': # move back to previous form
            stage -= 1
            myState['page'] = stage

            iq.swapAttributeValues("from", "to")
            iq['type'] = 'result'
            iq.command['status'] = 'executing'
            form = self.pages[stage]
            # apply old settings to this form
            for k,v in myState['data'][stage].iteritems():
                form[k] = v
            self.onShowForm(form, stage, myState)

            iq.command.children = [form.getElement()]
            if myState['page'] > 0:
                validActions = ['next', 'prev']
            else:
                validActions = ['next']
            ok = True

        if validActions <> []:
            a = domish.Element((None, "actions"))
            for ac in validActions:
                a.addElement(ac)
            iq.command.children.insert(0, a)
        if ok: # this indicates the iq has been modified by swapping to/from etc
            return iq
    def onShowForm(self, form, stage, state):
        "Override this method to modify a form before it gets sent to the requester"
        pass
    def onComplete(self, xmlstream, jid, pages):
        pass

