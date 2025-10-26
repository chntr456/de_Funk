from abc import ABC, abstractmethod

class Ingestor(ABC):
    def __init__(self, storage_cfg):
        self.storage_cfg = storage_cfg

    @abstractmethod
    def run_all(self, **kwargs):
        pass
