import machine, time, sys, utime, _thread
import gsm, network
import socket
from tools import unquote, isipv4
import json
import uping
from microdot_asyncio import Microdot

version = 0.9

config = './params.cfg'
dbname = './hosts.cfg'
running = True

hosts = dict()
params = dict()

app = Microdot()

def read_params(configfilename):
    global params
    try:
        with open(configfilename, 'r') as f:
            params = json.load(f)
    except:
            print('Configuration read error! System halted.')
            sys.exit()

def connect_wifi(WLAN_ID, WLAN_PASS):
    # Init wifi
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected() == False:
        wlan.connect(WLAN_ID, WLAN_PASS)
        print('Connecting to wifi...', end='')
        while wlan.isconnected() == False:
            print('.', end='')
            time.sleep(2)
    print('OK ' + wlan.ifconfig()[0])

def clock_sync(_server = 'time.nmisa.org', _tz = '<+03>-3'):
    print('Syncronizing the clock...', end='')
    R = machine.RTC()
    R.ntp_sync(server = _server, tz = _tz)
    while R.synced() == False:
        print('.', end='')
        time.sleep(2)
    print('OK ' + utime.strftime ('%c'))

def init_gsm(GSM_APN, GSM_USER, GSM_PASS):
    # Power on the GSM module
    GSM_PWR = machine.Pin(4, machine.Pin.OUT)
    GSM_RST = machine.Pin(5, machine.Pin.OUT)
    GSM_MODEM_PWR = machine.Pin(23, machine.Pin.OUT)
    GSM_PWR.value(0)
    GSM_RST.value(1)
    GSM_MODEM_PWR.value(1)
    # Init PPPoS
    # gsm.debug(True)  # Uncomment this to see more logs, investigate issues, etc.
    gsm.start(tx=27, rx=26, apn=GSM_APN, user=GSM_USER, password=GSM_PASS)
    print('Waiting for AT command response...', end='')
    for retry in range(20):
        if gsm.atcmd('AT'):
            break
        else:
            print('.', end='')
            time.sleep(2)
    else:
        raise Exception("Modem not responding!")
    print('OK')

def connect_gsm():
    print("Connecting to GSM...")
    gsm.connect()
    while gsm.status()[0] != 1:
        pass
    print('GSM IP:', gsm.ifconfig()[0])

def read_db(dbfilename):
    global hosts
    try:
        with open(dbfilename, 'r') as f:
            hosts = json.load(f)
    except:
        if gsm.sendSMS(params["ADMIN_PHONE"], 'Database read error!'):
            print('Database read error! SMS has been delivered')
        else:
            print('Database read error! SMS hasn\'t been delivered')

def save_db(dbfilename):
    global hosts
    try:
        with open(dbfilename, 'w') as f:
            json.dump(hosts, f)
    except:
        if gsm.sendSMS(params["ADMIN_PHONE"], 'Database save error!'):
            print('Database save error! SMS has delivered')
        else:
            print('Database save error! SMS hasn\'t been delivered')

@app.route('/send')
async def send_sms(request):
    print(request)
    req = request.split('\n')[0].split()[1].split('/')
#    print(str(unquote(req[3]), 'ucs2'))
    if gsm.sendSMS(req[2], str(unquote(req[3]), 'ucs2')):
        server.send("HTTP/1.0 200 OK\r\n")
    else:
        server.send("HTTP/1.0 502 Bad Gateway\r\n")

def hosts_get(request):
    global hosts
    req = request.split('\n')[0].split()[1].split('/')
    try:
        if req[2]:
            if isipv4(str(unquote(req[2]), 'ucs2')):
                print('GET ', req)
                server.send("HTTP/1.0 200 OK\r\n")
            else:
                print(hosts)
                server.send("HTTP/1.0 400 Bad request\r\n")
        else:
# здесь будет формироваться таблица статусов мониторящихся хостов            
            server.send("HTTP/1.0 200 OK\r\n")
    except:
        server.send("HTTP/1.0 503 Service Unavailable\r\n")

def hosts_put(request):
    global hosts
    req = request.split('\n')[0].split()[1].split('/')
    req_ip = str(unquote(req[2]), 'ucs2')
    try:
        if req_ip:
            if isipv4(req_ip):
#                print('PUT ', req)
                hosts[req_ip]=[False, int(utime.time())]
                save_db(dbname)
                server.send("HTTP/1.0 201 Created\r\n")
            else:
#                print(hosts)
                server.send("HTTP/1.0 400 Bad request\r\n")
        else:
            server.send("HTTP/1.0 405 Method Not Allowed\r\n")
    except:
        server.send("HTTP/1.0 503 Service Unavailable\r\n")

def hosts_delete(request):
    global hosts
    req = request.split('\n')[0].split()[1].split('/')
    req_ip = str(unquote(req[2]), 'ucs2')
    try:
        if req_ip:
            if isipv4(req_ip):
#                print('DELETE ', req)
                hosts.pop(req_ip, None)
                save_db(dbname)
                server.send("HTTP/1.0 200 OK\r\n")
            else:
                server.send("HTTP/1.0 400 Bad Request\r\n")
        else:
            server.send("HTTP/1.0 405 Method Not Allowed\r\n")
    except:
        server.send("HTTP/1.0 503 Service Unavailable\r\n")

def check_oldest():
    global hosts
    global running
    count = 2 
    while running:        
        key = min(hosts, key = lambda k: hosts[k][1])
        prev_result = hosts[key][0]
        result = uping.ping(key, count=count, quiet=True, size=64)
        ping_result = (result[1] == count)
        hosts[key] = [ping_result, int(utime.time())]
        if ping_result ^ prev_result:
            if ping_result:
                gsm.sendSMS(params["ADMIN_PHONE"], key + ' has been resurrected!')
            else:
                gsm.sendSMS(params["ADMIN_PHONE"], key + ' died!')
        time.sleep(1)

# main process
read_params(config)
connect_wifi(params['WLAN_ID'], params['WLAN_PASS'])
clock_sync()
init_gsm(params['GSM_APN'], params['GSM_USER'], params['GSM_PASS'])
read_db(dbname)
app.run()
print('Waiting for requests...')
#    server.add_route("/send", send_sms)
#    server.add_route("/hosts", hosts_get, method="GET")
#    server.add_route("/hosts", hosts_put, method="PUT")
#    server.add_route("/hosts", hosts_delete, method="DELETE")
#    server.start()
