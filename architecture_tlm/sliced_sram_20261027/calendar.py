"""Exact append fast path; does not change arbitration or hardware resources."""
from architecture_tlm.scheduling_v2_20261027.calendar import ReadyCalendar


class FastCalendar(ReadyCalendar):
    def _fit(self,resource,start,duration,period):
        events=self.calendar[resource]
        if not events or start>=events[-1][1]:return start
        return super()._fit(resource,start,duration,period)
