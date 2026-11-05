"""Original FullDecode plus sequential-phase calendar collection."""
from architecture_tlm.unified_v6.model import FullDecode

class SchedulingDecode(FullDecode):
    def phase(self,name,token,layer,ready,fn):
        if hasattr(self.s,'advance'):self.s.advance(ready)
        return super().phase(name,token,layer,ready,fn)
