import time
import asyncio

class SleepInterval:
    """
    Luokka, jonka oliota voi käyttää
        - prosessin tai säikeen ajastukseen
        - taskin ajastukseen

    Metodit:
        Sleep: prosessin tai säikeen ajastettu suorittaminen
        SleepAsync: taskin ajastettu suorittaminen
    """
    def __init__(self, s=1):
        """
        Ajastusolion muodostinmetodi
        Alustetaan olion jäsenmuuttujat
        """
        self.s = s # tavoiteltava toistoaika
        self.delay = s # toistoajan vaatima laskennallinen Sleep-viiveen kesto
        self.now = time.time() - s # edellisen taskin suorituskerran aikaleima
        self.errorcount = 0 # kadotettujen aikaslotien määrä
        self.start = self.now + s # olion muodostamisaikaleima
    def Sleep(self, s=0, dump=0):
        """
        Metodi, josta palataan jatkuvasti tietyn toistoajan välein.
        Odotusaika funktiossa kulutetaan time.sleep-kutsussa.
        Funktion pitämä toistoaika säilyy keskimäärin oikeana

        Args:
            s (float, optional): intervalli sekunteina
                0 - käytetään muodostimen toistoaikaa (oletus)
            dump (int, optional): dumppitulostuksen ohjaus
                0 - ei tulosteta (oletus)
                1 -tulostetaan
        Return:
            ei mitään
        """
        now = time.time() # aikaleima kutsuhetkellä
        if s > 0: # jos annettu toistoaika, niin
            self.s = s
        else:
            s = self.s
        delay = now - self.now # aikaleimojen välinen viive (tavoite s)
        error = s - delay # halutun ja toteutuneen ajan erotus
        self.now = now # päivitetään edellisen kutsun aikaleima tämän kutsun leimaan
        self.delay = self.delay + error # päivitetään laskettu odotusaika virheen mukaan


        # jos laskettu odotusaika on negatiivinen, niin jätetään ainakin yksi intervalli väliin
        while self.delay < 0: 
            self.delay = self.delay + s

            # dumppitulostusten laskenta ja tulostus, jos pyydetään
            if dump:
                self.errorcount = self.errorcount + 1
        if dump:
            print(f"{now:.3f} {self.start:.3f} {self.delay:6.3f} {delay:6.3f} {error:6.3f} {self.errorcount:4d}", end="")
            self.start = self.start + s

        # lopuksi jäädään uinumaan lasketuksi ajaksi
        time.sleep(self.delay)

    async def SleepAsync(self, s=0, dump=0):
        """
        Task-metodi, josta palataan jatkuvasti tietyn toistoajan välein.
        Odotusaika funktiossa kulutetaan time.sleep-kutsussa.
        Funktion pitämä toistoaika säilyy keskimäärin oikeana

        Args:
            s (float, optional): intervalli sekunteina
                0 - käytetään muodostimen toistoaikaa (oletus)
            dump (int, optional): dumppitulostuksen ohjaus
                0 - ei tulosteta (oletus)
                1 -tulostetaan
        Return:
            ei mitään
        """
        now = time.time() # aikaleima kutsuhetkellä
        if s > 0: # jos annettu toistoaika, niin
            self.s = s
        else:
            s = self.s
        delay = now - self.now # aikaleimojen välinen viive (tavoite s)
        error = s - delay # halutun ja toteutuneen ajan erotus
        self.now = now # päivitetään edellisen kutsun aikaleima tämän kutsun leimaan
        self.delay = self.delay + error # päivitetään laskettu odotusaika virheen mukaan

        # jos laskettu odotusaika on negatiivinen, niin jätetään ainakin yksi intervalli väliin
        while self.delay < 0: 
            self.delay = self.delay + s

            # dumppitulostusten laskenta ja tulostus, jos pyydetään
            if dump:
                self.errorcount = self.errorcount + 1
        if dump:
            print(f"{now:.3f} {self.start:.3f} {self.delay:6.3f} {delay:6.3f} {error:6.3f} {self.errorcount:4d}", end="")
            self.start = self.start + s

        # lopuksi jäädään uinumaan lasketuksi ajaksi
        await asyncio.sleep(self.delay)
