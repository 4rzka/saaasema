from guizero import App, Text, TextBox, PushButton, Box
from threading import Thread, Lock
from subprocess import Popen
from socket import socket, SOCK_DGRAM
from SleepInterval import  SleepInterval

from azure.eventhub import TransportType
from azure.eventhub import EventHubConsumerClient

from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import CloudToDeviceMethod, CloudToDeviceMethodResult

from json import loads, dumps

from time import time

'''UI - lämpötilahälyttimen graafinen käyttöliittymä

Käyttöliittymä kommunikoi UDP-yhteydellä
hälyttimen palvelinsäikeen kanssa.
'''
class UI:
    EVENT_HUB_CONNECTION_STR = \
        "Endpoint=sb://ihsuproddbres018dednamespace.servicebus.windows.net/;"\
        "SharedAccessKeyName=service;"\
        "SharedAccessKey=8Wl2FDVEj+l3yQFaQLYLEjA8VDAeu2WikpM1Tb99FGg=;"\
        "EntityPath=iothub-ehub-iot-room-d-4576348-31ad10dbf4"
    IOT_HUB_CONNECTION_STR = "HostName=iot-room-data-lahtinen.azure-devices.net;"\
        "SharedAccessKeyName=service;"\
        "SharedAccessKey=8Wl2FDVEj+l3yQFaQLYLEjA8VDAeu2WikpM1Tb99FGg="

    DEVICE_ID = "lampotilahalytin"
    def __init__(self):
        # käyttöliittymän rakentaminen
        self.app = App(title='Hälytinkäyttöliittymä - IoT hub', layout='grid', height=100)
        self.box = Box(self.app, layout='grid', grid=[0,1])
        self.app.when_closed = self.when_closed
        self.text_status = Text(self.app, text="Lämpö: , Raja: , Häly:", grid=[0,0])
        self.text_get = Text(self.box, text="Hälytysraja: ", grid=[0,0])
        self.textbox_get = TextBox(self.box, grid=[1,0])#, command=self.on_button_get)
        self.pushbutton_get = PushButton(self.box, text="Käytä digitaalista",
            grid=[2,0], command=self.on_button_get)
        self.pushbutton_set = PushButton(self.box, text="Käytä analogista",
            grid=[3,0], command=self.on_button_set)
        
        # säikeiden kommunikontiobjektit
        self.lukko = Lock()

        # samanaikaisuuden objektit
        self.toimi = Thread(target=self.toiminta)

        self.asiakas = EventHubConsumerClient.from_connection_string(
            conn_str=self.EVENT_HUB_CONNECTION_STR,
            consumer_group="$default"
            )
        
        # Create IoTHubRegistryManager
        self.registry_manager = IoTHubRegistryManager(self.IOT_HUB_CONNECTION_STR)


    def main(self):
        # käyttöliittymänäkymän käynnistäminen
        self.app.after(1000, self.when_started)
        self.app.display()

        # säikeen odotus, palvelimen sammutus ja odotus
        self.toimi.join()

        try:
            deviceMethod = CloudToDeviceMethod(method_name='stop')
            self.registry_manager.invoke_device_method(self.DEVICE_ID, deviceMethod)
        except:
            pass

    def on_event_batch(self, partition_context, events):
        for event in events:
            dt = loads(event.body_as_str())
            self.text_status.value =\
                f"Lämpö: {float(dt['Lämpö']):.2f}, "\
                f"Raja: {float(dt['Raja']):.2f}, "\
                f"Häly: {event.properties['Hälytys'.encode()].decode()}, "\
                f"Viive: {round(round(time(), 3)-float(dt['Aika']), 3):.3f}"
        partition_context.update_checkpoint()

    def on_error(self, partition_context, error):
        # Put your code here. partition_context can be None in the on_error callback.
        if partition_context:
            print("An exception: {} occurred during receiving from Partition: {}.".format(
                partition_context.partition_id,
                error
            ))
        else:
            print("An exception: {} occurred during the load balance process.".format(error))

    def toiminta(self):
        print('Toiminta aloittaa')

        self.asiakas.receive_batch(
            on_event_batch=self.on_event_batch,
            on_error=self.on_error
        )

        print('Toiminta lopettaa')

    def on_button_get(self):
        self.lukko.acquire()
        raja = self.textbox_get.value
        self.lukko.release()

        try:
            deviceMethod = CloudToDeviceMethod(method_name='setRaja', payload=raja)
            self.registry_manager.invoke_device_method(self.DEVICE_ID, deviceMethod)
        except:
            pass

    def on_button_set(self):
        try:
            deviceMethod = CloudToDeviceMethod(method_name='setRajaAnalog')
            self.registry_manager.invoke_device_method(self.DEVICE_ID, deviceMethod)
        except:
            pass
        
    def when_closed(self):
        self.asiakas.close()
        self.app.destroy()

    def when_started(self):
        self.toimi.start()

if __name__ == '__main__':
    UI().main()