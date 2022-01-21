# Fronius Datamanager Solar.API Integration (Inverter Web Interface)
import logging
import requests
import time

logger = logging.getLogger(__name__.rsplit(".")[-1])


class Fronius:

    cacheTime = 10
    config = None
    configConfig = None
    configFronius = None
    consumedW = 0
    fetchFailed = False
    generatedW = 0
    generatedW2 = 0
    akku = 0
    importW = 0
    exportW = 0
    lastFetch = 0
    master = None
    serverIP = None
    serverPort = 80
    serverIP2 = None
    serverPort2 = 80
    status = False
    timeout = 5 
    voltage = 0

    def __init__(self, master):
        self.master = master
        self.config = master.config
        try:
            self.configConfig = master.config["config"]
        except KeyError:
            self.configConfig = {}
        try:
            self.configFronius = master.config["sources"]["Fronius"]
        except KeyError:
            self.configFronius = {}
        self.status = self.configFronius.get("enabled", False)
        self.serverIP = self.configFronius.get("serverIP", None)
        self.serverPort = self.configFronius.get("serverPort", "80")
        self.serverIP2 = self.configFronius.get("serverIP2", None)
        self.serverPort2 = self.configFronius.get("serverPort2", "80")


        # Unload if this module is disabled or misconfigured
        if (not self.status) or (not self.serverIP) or (int(self.serverPort) < 1):
            self.master.releaseModule("lib.TWCManager.EMS", "Fronius")
            return None

    def getConsumption(self):

        if not self.status:
            logger.debug("Fronius EMS Module Disabled. Skipping getConsumption")
            return 0

        # Perform updates if necessary
        #self.update()

        generated = self.getGeneration()

        if not self.akku:
            self.akku = 0

        consumed = generated + float(self.consumedW) + float(self.akku)

        return consumed

    def getGeneration(self):

        if not self.status:
            logger.debug("Fronius EMS Module Disabled. Skipping getGeneration")
            return 0

        # Perform updates if necessary
        self.update()

        # Return generation value
        if not self.generatedW:
            self.generatedW = 0
        if not self.generatedW2:
            self.generatedW2 = 0

        return float(self.generatedW) + float(self.generatedW2)

    def getInverterData(self):
        url = "http://" + self.serverIP + ":" + self.serverPort
        url = (
            url
            + "/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceID=1&DataCollection=CommonInverterData"
        )

        return self.getInverterValue(url, False)

    def getInverterValue(self, url, shouldSetFailed):

        # Fetch the specified URL from the Fronius Inverter and return the data

        try:
            r = requests.get(url, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            logger.log(
                logging.INFO4,
                "Error connecting to Fronius Inverter to fetch sensor value",
            )
            logger.debug(str(e))
            if shouldSetFailed:
                self.fetchFailed = True
            return False

        r.raise_for_status()
        jsondata = r.json()
        return jsondata

    def getMeterData(self, ip, port, shouldSetFailed):
        url = "http://" + ip + ":" + port
        url = url + "/solar_api/v1/GetPowerFlowRealtimeData.fcgi?Scope=System"

        return self.getInverterValue(url, shouldSetFailed)

    def getSmartMeterData(self):
        url = "http://" + self.serverIP + ":" + self.serverPort
        url = url + "/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System"

        return self.getInverterValue(url, False)


    def update(self):

        if (int(time.time()) - self.lastFetch) > self.cacheTime:
            # Cache has expired. Fetch values from Fronius inverter.

            self.fetchFailed = False

            #inverterData = self.getInverterData()
            #if inverterData:
            #    try:
            #        if "UAC" in inverterData["Body"]["Data"]:
            #            self.voltage = inverterData["Body"]["Data"]["UAC"]["Value"]
            #    except (KeyError, TypeError) as e:
            #        logger.log(
            #            logging.INFO4, "Exception during parsing Inveter Data (UAC)"
            #        )
            #        logger.debug(e)

            meterData = self.getMeterData(self.serverIP, self.serverPort, True)
            if meterData:
                try:
                    self.generatedW = meterData["Body"]["Data"]["Site"]["P_PV"]
                    self.akku = meterData["Body"]["Data"]["Site"]["P_Akku"]
                    logger.info(
                        "generatedW",
                        self.generatedW
                    )
                except (KeyError, TypeError) as e:
                    self.generatedW = 0
                    self.akku = 0
                    logger.log(
                        logging.INFO4,
                        "Exception during parsing Meter Data (Generation)",
                    )
                    logger.debug(e)

            meterData2 = self.getMeterData(self.serverIP2, self.serverPort2, False)
            if meterData2:
                try:
                    self.generatedW2 = meterData2["Body"]["Data"]["Site"]["P_PV"]
                    logger.info(
                        "generatedW2",
                        self.generatedW2
                    )
                except (KeyError, TypeError) as e:
                    self.generatedW2 = 0
                    logger.log(
                        logging.INFO4,
                        "Exception during parsing Meter Data 2 (Generation)",
                    )
                    logger.debug(e)

            smartMeterData = self.getSmartMeterData()
            if smartMeterData:
                try:
                    self.consumedW = smartMeterData["Body"]["Data"]["0"]["PowerReal_P_Sum"]
                    self.voltage = smartMeterData["Body"]["Data"]["0"]["Voltage_AC_Phase_1"] 
                except (KeyError, TypeError) as e:
                    self.consumedW = 0
                    logger.log(
                        logging.INFO4,
                        "Exception during parsing Smart Meter Data (Consumption)",
                    )
                    logger.debug(e)

   

            # Update last fetch time
            if self.fetchFailed is not True:
                self.lastFetch = int(time.time())

            return True
        else:
            # Cache time has not elapsed since last fetch, serve from cache.
            return False
