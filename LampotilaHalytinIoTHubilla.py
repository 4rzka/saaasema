from threading import Thread, Lock
from SleepInterval import SleepInterval

from time import sleep, time

import grove.adc_8chan_12bit as g

from gpiozero import LED
from gpiozero import Button

from statistics import median
from random import uniform

from os import system

from select import select
from sys import stdin

from socket import socket, SOCK_DGRAM

from azure.iot.device import IoTHubDeviceClient, Message, MethodResponse

from json import dumps

class Halytin:
    CONNECTION_STRING = "HostName=iot-room-data-lahtinen.azure-devices.net;DeviceId=lampotilahalytin;SharedAccessKey=OLlMAwFkjDQUL6ag+Wcmjr6XQjLMZDB59yoY63Ob/MI="
    def __init__(self):
        # luodaan säikeet saikeet-atribuuttiin
        self.saikeet = list()
        self.saikeet.append(Thread(target=self.konsoli))
        self.saikeet.append(Thread(target=self.lampotila))
        self.saikeet.append(Thread(target=self.halytysraja))
        self.saikeet.append(Thread(target=self.paivita))
        # palvelinsäikeen käynnistys
        self.saikeet.append(Thread(target=self.palvelin))
        # IoT hub säikeet
        self.saikeet.append(Thread(target=self.laitelahettaja))
        self.saikeet.append(Thread(target=self.laitemetodikuuntelija,\
            daemon=False)) # daemon=True => säie lopetetaan pääsäikeen mukaan

        # lukko (mutex) - olio kriittisen alueen suojaamiseksi
        self.lukko = Lock()

        # kriittisen alueen atribuutit
        self.loppu = False # säikeiden lopetuslippu
        self.lampo = 20 # mitattu ja suodatettu lämpötila
        self.raja = 15 # hälytysraja
        # rajatiedon analogisen asetuksen lippu
        self.rajatila = False # digitaalinen

        # lämpötilojen keskiarvosuodatuksen lista ja sen indeksilaskuri
        self.lammot = [self.lampo, self.lampo, self.lampo]
        self.cnt = 0

        # lämpötilatiedoston polku
        self.temp_sensor = '/sys/bus/w1/devices/28-00000c549f1c/w1_slave'

        # soketin luonti palvelinsäiettä varten
        self.sock = socket(type=SOCK_DGRAM)
        self.sock.bind(('localhost',10000))

        self.client = IoTHubDeviceClient.create_from_connection_string(self.CONNECTION_STRING)

    def main(self):
        print("Lämpötilahälyttimen toiminta alkaa")

        for saie in self.saikeet:
            saie.start()

        for saie in self.saikeet:
            saie.join()

        print("Lämpötilahälyttimen toiminta loppuu")

    def konsoli(self):
        print("Käyttöliittymä käynnistyy")

        self.lukko.acquire()
        while not self.loppu:
            self.lukko.release()
            # odotetaan näppäimistötietoa timeoutilla
            i, o, e = select([stdin], [], [], 1)
            if i:
                if input() == "":
                    with self.lukko:
                        self.loppu = True
                        # lähetetään itselle palvelimen lopetuskomento
                        self.sock.sendto('stop'.encode(), ('localhost', 10000))
                else:
                    print("Paina enter lopettaaksesi")
            self.lukko.acquire()

        self.lukko.release()
        print("Käyttöliittymä lopettaa")

    def paivita(self):
        print("Päivitys käynnistyy")

        self.lukko.acquire()
        while not self.loppu:
            print(f"\rLämpötila: {self.lampo:5.2f} - Hälytysraja: {self.raja:5.2f}", end="")
            self.lukko.release()
            sleep(1)
            self.lukko.acquire()

        self.lukko.release()
        print("Päivitys lopettaa")

    def lampotila(self):
        print("Lämpötilan mittaus käynnistyy")

        led = LED(27)

        sleepInterval = SleepInterval(2)

        self.lukko.acquire()
        while not self.loppu:
            self.lampo = self.suodata(self.lueLampo())

            if self.lampo > self.raja:
                led.blink()
            else:
                led.off()

            self.lukko.release()
            sleepInterval.Sleep()
            self.lukko.acquire()

        self.lukko.release()
        led.off()
        print("Lämpötilan mittaus lopettaa")

    def lueLampo(self):
        try:
            f = open(self.temp_sensor, 'r')
            lns = f.readlines()
            f.close()

            while lns[0].strip()[-3:] != 'YES':
                sleep(0.2)
                f = open(self.temp_sensor, 'r')
                lns = f.readlines()
                f.close()

            la = lns[1].find('t=')
            if la != -1:
                return round(float(lns[1].strip()[la+2:])/1000, 2)
            else:
                return self.lampo
        except:
            return self.lampo + uniform(-3, 3)

    def suodata(self, lampo):
        self.lammot[self.cnt] = lampo
        self.cnt = (self.cnt+1)%3
        return median(self.lammot)

    def halytysraja(self):
        print("Hälytysraja käynnistyy")

        adc = g.Pi_hat_adc()

        sleepInterval = SleepInterval(4)

        self.lukko.acquire()
        while not self.loppu:
            # jos rajatila on tosi, niin silloin luetaan
            if self.rajatila:
                self.raja = round(adc.get_nchan_vol_milli_data(0)/33/100*20+10, 2)

            self.lukko.release()
            sleepInterval.Sleep()
            self.lukko.acquire()

        self.lukko.release()
        print("Hälytysraja lopettaa")

    '''palvelin - säie, joka hoitaa käyttöliittymän pyynnöt

    Säie lukee asiakaan komentoja ja toimii niiden mukaan.
    Säie lopettaa, kun saa stop-komennon, jolloin ilmoittaa myös muille
    säikeille lopetuksesta.

    Komennot
    --------
    stop - palvelimen pysäytys
    get - tietojen pyyntö
    set - analogisen lämpötilarajan käyttöönotto
    set <lämpötilaraja> - digitaalisen lämpötilarajan käyttöönotto
    '''
    def palvelin(self):
        print("Palvelin aloittaa")
        try:
            # odotellaan, luetaan ja muunnetaan merkkijonoksi komento
            data, address = self.sock.recvfrom(4096)
            dt = data.decode().split()
            while dt[0] != 'stop': # eihän lopetus
                
                if dt[0] == 'get': # tietojen pyyntö
                    with self.lukko:
                        data = f"get {self.lampo} {self.raja} {self.lampo>self.raja}".encode()
                if dt[0] == 'set': # lämpötilarajan asetus
                    if len(dt) == 2: # annetaan digitaalinen lämpötilaraja
                        try:
                            raja = round(float(dt[1]), 2)
                            with self.lukko:
                                self.raja = raja
                                self.rajatila = False
                        except:
                            pass # ei annettu raja-arvoa liukulukuna
                    else: # palataan analogiseen
                        with self.lukko:
                            self.rajatila = True

                # lähetetaan vastays pyynnön lähettäjälle
                self.sock.sendto(data, address)

                # ja uuden pyynnön odotus
                data, address = self.sock.recvfrom(4096)
                dt = data.decode().split()
                
        except:
            self.sock.close()

        # mutexia (lukkoa) käyttäen loppu-lipun asetus lopetettaessa
        with self.lukko:
            self.loppu = True
        print("Palvelin lopettaa")

    '''laitelahettaja - säiemetodi tietojen lähettämiseksi IoT hubille
    '''
    def laitelahettaja(self):
        print('Laitelähettäjä aloittaa')
        sleepInterval = SleepInterval(4)
        sleepInterval.Sleep()

        self.lukko.acquire()
        while not self.loppu:
            self.lukko.release()

            sanoma = Message(
                dumps({"temp": self.lampo,
                        "limit": self.raja,
                        "time": round(time(), 3)}))
            sanoma.custom_properties["Hälytys"] = f"{self.lampo > self.raja}"
            self.client.send_message(sanoma)

            sleepInterval.Sleep()
            self.lukko.acquire()

        self.lukko.release()
        print('Laitelähettäjä lopettaa')

    '''laitemetodikuuntelija - säiemetodi IoT hubin sanomien käsittelyyn
    '''
    def laitemetodikuuntelija(self):
        print('Laitemetodikuuntelija aloittaa')

        self.lukko.acquire()
        while not self.loppu:
            self.lukko.release()
            pyynto = self.client.receive_method_request(timeout=1)
            if pyynto: # eihän timeout
                if pyynto.name == "setRaja":
                    try:
                        with self.lukko:
                            self.raja = round(float(pyynto.payload), 2)
                            self.rajatila = False
                    except ValueError:
                        vastaus_tieto = "Vastaus: ei numeerinen hälytysraja"
                        vastaus_tila = 400
                    else:
                        vastaus_tieto = "Vastaus: suoritettu setRaja"
                        vastaus_tila = 200
                elif pyynto.name == "setRajaAnalog":
                    with self.lukko:
                        self.rajatila = True
                    vastaus_tieto = "Vastaus: suoritettu setRajaAnalog"
                    vastaus_tila = 200
                elif pyynto.name == "stop":
                    with self.lukko:
                        self.loppu = True
                        # lähetetään itselle palvelimen lopetuskomento
                    self.sock.sendto('stop'.encode(), ('localhost', 10000))
                    vastaus_tieto = "Vastaus: suoritettu stop"
                    vastaus_tila = 200
                else:
                    vastaus_tieto = "Vastaus: ei sallittu komento"
                    vastaus_tila = 404
                vastaus = MethodResponse(pyynto.request_id, vastaus_tila, payload=vastaus_tieto)
                self.client.send_method_response(vastaus)

            self.lukko.acquire()

        self.lukko.release()
        print('Laitemetodikuuntelija lopettaa')

'''Halytin-olion luonti ja main-metodin käynnistys käynnistettäessä
'''
if __name__ == '__main__':
    Halytin().main()
