from guizero import App, Text, TextBox, PushButton, Box
from threading import Thread, Lock
from subprocess import Popen
from socket import socket, SOCK_DGRAM
from SleepInterval import  SleepInterval

'''UI - lämpötilahälyttimen graafinen käyttöliittymä

Käyttöliittymä kommunikoi UDP-yhteydellä
hälyttimen palvelinsäikeen kanssa.
'''
class UI:
    def __init__(self):
        # käyttöliittymän rakentaminen
        self.app = App(title='Lämpötilamonitori', layout='grid', height=100)
        self.box = Box(self.app, layout='grid', grid=[0,1])
        self.app.when_closed = self.when_closed
        self.text_status = Text(self.app, text="Lämpötila : , Raja: , Häly:", grid=[0,0])
        self.text_get = Text(self.box, text="Hälytysraja: ", grid=[0,0])
        self.textbox_get = TextBox(self.box, grid=[1,0])#, command=self.on_button_get)
        self.pushbutton_get = PushButton(self.box, text="Käytä digitaalista",\
            grid=[2,0], command=self.on_button_get)
        self.pushbutton_set = PushButton(self.box, text="Käytä analogista",\
            grid=[3,0], command=self.on_button_set)
        
        # säikeiden kommunikontiobjektit
        self.lukko = Lock()
        self.lippu = False
        self.soketti = socket(type=SOCK_DGRAM)
        self.sokettilukko = Lock()

        # samanaikaisuuden objektit
        self.toimi = Thread(target=self.toiminta)
        self.palvelin = Popen(args=('python3',\
            'LampotilaHalytinIoTHubilla.py'))

    def main(self):
        # käyttöliittymänäkymän käynnistäminen
        self.app.after(1000, self.when_started)
        self.app.display()

        # säikeen odotus, palvelimen sammutus ja odotus
        self.toimi.join()
        with self.sokettilukko:
            self.soketti.sendto("stop".encode(), ('localhost', 10000))
        self.palvelin.wait()

    def toiminta(self):
        print('Toiminta aloittaa')
        sleepInterval = SleepInterval(1)
        sleepInterval.Sleep()
        sleepInterval.Sleep()

        self.lukko.acquire()
        while self.lippu:
            self.lukko.release()
            with self.sokettilukko:
                self.soketti.sendto("get".encode(), ('localhost', 10000))
                self.soketti.settimeout(1)
                try:
                    data, address = self.soketti.recvfrom(4096)
                except:
                    dt = []
                else:
                    dt = data.decode().split()
            with self.lukko:
                if len (dt) == 4 and self.lippu:
                    self.text_status.value =\
                        f"Lämpö: {float(dt[1]):.2f} °C Raja: {float(dt[2]):.2f} °C Häly: {dt[3]}"
            sleepInterval.Sleep()
            self.lukko.acquire()
        self.lukko.release()
        print('Toiminta lopettaa')

    def on_button_get(self):
        self.lukko.acquire()
        raja = self.textbox_get.value
        self.lukko.release()
        with self.sokettilukko:
            self.soketti.sendto(\
                f"set {raja}".encode(),\
                ('localhost', 10000))
            self.soketti.recvfrom(4096)

    def on_button_set(self):
        with self.sokettilukko:
            self.soketti.sendto(\
                f"set".encode(),\
                ('localhost', 10000))
            self.soketti.recvfrom(4096)

    def when_closed(self):
        with self.lukko:
            self.lippu = False

        self.app.destroy()

    def when_started(self):
        with self.lukko:
            self.lippu = True
        self.toimi.start()

if __name__ == '__main__':
    UI().main()