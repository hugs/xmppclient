import xpaths, namespaces
from twisted.words.protocols.jabber import jid
from twisted.internet import reactor
from twisted.internet.utils import getProcessOutput
import DataForms
from utils import messageStanza

namespaces.COMMANDS = 'http://jabber.org/protocol/commands'
xpaths.EXECUTE_COMMAND = "/command[@xmlns='http://jabber.org/protocol/commands']"

def shellCommand(cmdline, env={}, path='.', reactor=None, errortoo=1):
    "Returns a function which executes a command, and sends the output back to the sending JID"
    args = cmdline.split()
    executable = args[0]
    args.remove(executable)
    def f(xmlstream, iq):
        def sendResponse(result, xmlstream, to):
            xmlstream.send(messageStanza(to, result))
        # get command's output as a deferred..
        d = getProcessOutput(executable, args, env, path, reactor, errortoo)
        d.addCallback(sendResponse, xmlstream, iq['from'])
        
        iq['type'] = 'result'
        iq.swapAttributeValues("from", "to")
        iq.command['status'] = 'completed'
        return iq
    return f

def sshShell(user, host, keyfile, cmdline):
    "Returns a function which executes a command on a remote host via ssh"
    return shellCommand("ssh -i %s %s@%s %s" % (keyfile, user, host, cmdline))

class AdHocCommands:
    """"""
    name = namespaces.COMMANDS
    
    def __init__(self, entity, commands, testAuth=None, filterCommands=None):
        self.commands = commands
        self.testAuth = testAuth
        self.filterCommands = filterCommands
        self._entity = entity
        self._entity.disco.addNode(namespaces.COMMANDS, self)
        self._entity.disco.addFeature(namespaces.COMMANDS, self)
        self._entity.iq_set_hooks.addXPathHook(xpaths.EXECUTE_COMMAND, self.onExecuteCommand)

    def iteritems_for_jid(self, from_jid):
        "List commands available to a specific JID.. uses self.filterCommands if it's set"
        cmds = self.commands #.copy()
        #if self.filterCommands:
        #    cmds = self.filterCommands(cmds, from_jid)
        for i in cmds:
            yield {'node': i, 'name': self.commands.__title__(i)}

    def onExecuteCommand(self, iq):
        'Called when we receive a relevant iq'
        if self.testAuth:
            if not self.testAuth(jid.internJID(iq['from'])):
                pass # disallow
        node = iq.command['node']
        if node not in self.commands: # shouldn't really happen ever
            self._entity._xmlstream.send(messageStanza(iq['from'], "no such command"))
        cmd = self.commands[node]
        # call the function specified
        newIq = cmd(self._entity._xmlstream, iq)
        if newIq:
            # send the resulting iq back
            self._entity._xmlstream.send(newIq)

class CommandNode:
    def __init__(self, title, f):
        self.title = title
        if isinstance(f, DataForms.Wizard):
            self.function = f.processIq
        else:
            self.function = f

class CommandList:
    def __getitem__(self, key):
        if hasattr(self, key) and isinstance(getattr(self, key), CommandNode):
            return getattr(self, key).function
        raise AttributeError
    def __setitem__(self, key, value):
        setattr(self, key, value)
    def __iter__(self):
        for member in dir(self):
            if member[:2] == '__': continue
            if isinstance(getattr(self, member), CommandNode):
                yield member
    def __iteritems__(self):
        for member in dir(self):
            if member[:2] == '__': continue
            if isinstance(getattr(self, member), CommandNode):
                yield member, self[member]
    def __title__(self, key):
        if hasattr(self, key) and isinstance(getattr(self, key), CommandNode):
            return getattr(self, key).title
        raise AttributeError