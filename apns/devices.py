class DeviceRate(object):
    """Data Rate for specific equipments"""

    rate = 0

    def __init__(self, intf):
        model = intf.node.params['model']
        self.__getattribute__(model)(intf)

    def WEP1L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP2L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WOP2L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP3L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WOP20L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP200L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP30L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WOP30L(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WOP30LS(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP2ac(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate

    def WEP3ax(self, intf):
        modes = ['n', 'g', 'b']
        rates = [130, 54, 11]
        self.rate = rates[modes.index(intf.mode)]
        return self.rate


class CustomRange(object):
    range = 0

    def __init__(self, intf):
        self.customSignalRange(intf)

    def customSignalRange(self, intf):
        """Custom Signal Range
        mode: interface mode
        range: signal range (m)"""
        modes = ['a', 'g', 'b', 'n', 'ac', 'ax', 'be']
        ranges = [33, 33, 50, 70, 100, 100, 100]
        self.range = ranges[modes.index(intf.mode)]
        return self.range


class DeviceRange(object):
    """Range for specific equipments"""

    range = 100

    def __init__(self, node):
        self.__getattribute__(node.params['model'])()

    def WEP1L(self):
        self.range = 100
        return self.range

    def WEP2L(self):
        self.range = 100
        return self.range

    def WOP2L(self):
        self.range = 100
        return self.range

    def WEP3L(self):
        self.range = 100
        return self.range

    def WOP20L(self):
        self.range = 100
        return self.range

    def WEP200L(self):
        self.range = 100
        return self.range

    def WEP30L(self):
        self.range = 100
        return self.range

    def WOP30L(self):
        self.range = 100
        return self.range

    def WOP30LS(self):
        self.range = 100
        return self.range

    def WEP2ac(self):
        self.range = 100
        return self.range

    def WEP3ax(self):
        self.range = 100
        return self.range


class DeviceTxPower(object):
    """TX Power for specific equipments"""

    txpower = 0

    def __init__(self, intf):
        """get txpower"""
        model = intf.node.params['model']
        self.__getattribute__(model)(intf)

    def WEP1L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP2L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WOP2L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP3L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WOP20L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP200L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP30L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WOP30L(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WOP30LS(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP2ac(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower

    def WEP3ax(self, intf):
        modes = ['b', 'g', 'n']
        txpowers = [21, 18, 16]
        self.txpower = txpowers[modes.index(intf.mode)]
        return self.txpower
