from abc import ABC, abstractmethod


class PhotodiodesInterface(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def switch_to_vial(self, vial: int):
        pass

    @abstractmethod
    def measure(self, gain=8, bitrate=16, continuous_conversion=False):
        pass

class PumpInterface(ABC):
    @abstractmethod
    @property
    def stock_concentration():
        ...