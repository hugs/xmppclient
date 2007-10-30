from datetime import datetime

class ContactResource:
    def __init__(self, contact, name, priority=0, status='AVAILABLE', status_text=''):
        self.name = name
        self.priority = priority
        self.status = status
        self.status_text = status_text
        self.last_update = datetime.now()

class Contact:
    def __init__(self, bareJid):
        self.bareJid = bareJid
        self.resources = {}
    def addResource(self, name, **kwargs):
        self.resources[name] = ContactResource(self, name, **kwargs)
    def delResource(self, name):
        if name in self.resources:
            del self.resources[name]
    def bestResource(self):
        maxPri = 0
        best = None
        for v in self.resources.itervalues():
            if v.priority > maxPri:
                maxPri = v.priority
                best = v
        return best
