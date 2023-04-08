import json
from telnetlib import Telnet
from socket import gethostbyaddr
import time
import sys
import os
import threading

import logging
from logging.handlers import TimedRotatingFileHandler

from http.server import BaseHTTPRequestHandler, HTTPServer

programName = "disguise_status"
ip = "192.168.31.101"
port = 9864
logger = logging.getLogger(programName)

webpage_host_ip: str = "192.168.0.116"
webpage_port: int = 8083
webpage_enabled = True # TODO not implimented yet

lock = threading.RLock()

class DisguiseServer:
    def __init__(self, hostName, maxFPSLen):
        self.hostName = hostName
        self.maxFPSLen = maxFPSLen
        self.fpsArray = []
        
    #fpsArray = []

    def updateFPS(self, targetIP, targetPort):
        logger.debug("Updating fps for " + self.hostName)
        q = '{"query":{"q":"machineStatus ' + self.hostName+ '"}}'
        with Telnet(targetIP, targetPort) as tn:
            tn.write(q.encode('ASCII') + b'\r\n')
            buf_as_dict = json.loads(tn.read_until(b"}]}"))
            logger.debug(buf_as_dict)
            new_fps =  int(buf_as_dict['results'][0]['fps'])
            logger.debug("New FPS: " + str(new_fps))
            with lock:
                if (len(self.fpsArray) > self.maxFPSLen):
                    self.fpsArray.pop(0)
                self.fpsArray.append(new_fps)
            logger.debug("FPS Array: " + str(self.fpsArray))
                
    def logLatestFPS(self):
        logger.info(self.hostName + ": " + str(int(self.fpsArray[-1])) + " fps")
           
    def getJSON(self):
        jsonData = {}
        if (len(self.fpsArray) == 0):
            jsonData['fps'] = {}
            jsonData['fps']['average'] = 0
            jsonData['fps']['max'] = 0
            jsonData['fps']['min'] = 0
            jsonData['name'] = self.hostName

            return jsonData

        
        with lock:
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
            server.logLatestFPS()

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
    
class JSONServer(BaseHTTPRequestHandler):
    global disguiseSystem

    def do_GET(self):
        if self.path != '/' + programName + '/json':
            return
        with lock:
            logger.info("Responding to HTTP request")
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(disguiseSystem.getJSON()), "utf-8"))

def start_web_server(_web_server):
    _web_server.serve_forever()

            
def initialiseLogging():
    log_file_handler = TimedRotatingFileHandler(filename=os.path.join(sys.path[0], "runtime.log"), when='D', interval=1, backupCount=10,
                                        encoding='utf-8',
                                        delay=False)

    log_console_handler = logging.StreamHandler(sys.stdout)

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    log_file_handler.setFormatter(log_formatter)
    log_console_handler.setFormatter(log_formatter)


    logger.setLevel(logging.INFO)

    logger.addHandler(log_file_handler)
    logger.addHandler(log_console_handler)

    logger.info("Logger initialisation complete")


disguiseSystem = DisguiseSystem(ip, port, maxFPSLen=500)

if __name__ == '__main__':
    initialiseLogging()

    #logger.setLevel(logging.DEBUG)
    
    serversFound = disguiseSystem.findServers()
    logger.info(str(serversFound) + " servers discovered")

    webServer = HTTPServer((webpage_host_ip, webpage_port), JSONServer)
    logger.info("Server started http://%s:%s" % (webpage_host_ip, webpage_port))
    t = threading.Thread(target=start_web_server, args=(webServer,)).start()

    
    while True:
        disguiseSystem.updateFPS()
        logger.debug(json.dumps(disguiseSystem.getJSON()))
        time.sleep(0.5)
     
