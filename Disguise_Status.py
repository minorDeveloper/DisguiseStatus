import json
from telnetlib import Telnet
from socket import gethostbyaddr
import time
ip = "192.168.31.101"
port = 9864

class DisguiseServer:
    def __init__(self, hostName, maxFPSLen):
        self.hostName = hostName
        self.maxFPSLen = maxFPSLen
        
    fpsArray = []

    def updateFPS(self, targetIP, targetPort):
        q = '{"query":{"q":"machineStatus ' + self.hostName+ '"}}'
        with Telnet(targetIP, targetPort) as tn:
            tn.write(q.encode('ASCII') + b'\r\n')
            buf_as_dict = json.loads(tn.read_until(b"}]}"))
            new_fps =  int(buf_as_dict['results'][0]['fps'])

            if (len(self.fpsArray) > self.maxFPSLen):
                self.fpsArray.pop(0)
                self.fpsArray.append(new_fps)
           
    def getJSON(self):
        jsonData = {}
        if (len(self.fpsArray) == 0):
            jsonData['fps'] = {}
            jsonData['fps']['average'] = 0
            jsonData['fps']['max'] = 0
            jsonData['fps']['min'] = 0
            jsonData['name'] = self.hostName

            return jsonData

        averageFPS = sum(self.fpsArray) / len(self.fpsArray)
        maxFPS = max(self.fpsArray)
        minFPS = min(self.fpsArray)

        jsonData['fps'] = {}
        jsonData['fps']['average'] = averageFPS
        jsonData['fps']['max'] = maxFPS
        jsonData['fps']['min'] = minFPS
        jsonData['name'] = self.hostName

        return jsonData

class DisguiseSystem:
    def __init__(self, targetIP, targetPort=9864, maxFPSLen=60, lowFPSWarning=30, lowFPSWarningEnabled=True):
        self.targetIP = targetIP
        self.targetPort = targetPort
        self.maxFPSLen = maxFPSLen
        self.lowFPSWarning = lowFPSWarning
        self.lowFPSWarningEnabled = lowFPSWarningEnabled

        self.servers: DisguiseServer = []

    def updateFPS(self):
        for server in self.servers:
            server.updateFPS(self.targetIP, self.targetPort)

    def findServers(self):
        q = '{"query":{"q":"machineList"}}'
        self.servers = []
        with Telnet(self.targetIP, self.targetPort) as tn:
            tn.write(q.encode('ASCII') + b'\r\n')
            buf_as_dict = json.loads(tn.read_until(b"}]}"))
            server_json_list = buf_as_dict['results']
            for server_json in server_json_list:
                self.servers.append(DisguiseServer(hostName=server_json['name'], maxFPSLen=self.maxFPSLen))
        return len(self.servers)
        
    def getJSON(self):
        # json structure is each server's name, averaged, max, and min fps over the timeframe
        jsonData = {}
        serverDataArray = []

        for server in self.servers:
            serverDataArray.append(server.getJSON())
        jsonData['statusCode'] = 1
        jsonData['results'] = serverDataArray
        
        return jsonData
            

if __name__ == '__main__':
    disguiseSystem = DisguiseSystem(ip, port)
    disguiseSystem.findServers()
    #if len(disguiseSystem.findServers() == 0): print("Warning: no disguise servers found")
    while True:
        disguiseSystem.updateFPS()
        print(json.dumps(disguiseSystem.getJSON()))
        time.sleep(1)
     
