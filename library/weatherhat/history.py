import time

wind_degrees_to_cardinal = {
    0: "North",
    45: "North East",
    90: "East",
    135: "South East",
    180: "South",
    225: "South West",
    270: "West",
    315: "North West"
}


class HistoryEntry:
    __slots__ = 'value', 'timestamp'

    def __init__(self, value, timestamp=None):
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.value = value


class History:
    def __init__(self, history_depth=1200):
        self._history = []
        self.history_depth = history_depth

    def append(self, value, timestamp=None):
        self._history.append(HistoryEntry(value, timestamp=timestamp))
        self._history = self._history[-self.history_depth:]  # Prune the buffer

    def average(self, sample_over=None):
        history = self.history(sample_over)
        num_samples = len(history)
        return sum([entry.value for entry in history]) / float(num_samples)

    def timespan(self):
        return self._history[0].timestamp, self._history[-1].timestamp

    def min(self, sample_over=None):
        return min(self.history(sample_over))

    def max(self, sample_over=None):
        return max(self.history(sample_over))

    def median(self, sample_over=None):
        history = self.history(sample_over)
        median = int(len(history) / 2)
        return history[median].value

    def latest(self):
        return self._history[-1]

    def history(self, depth=None):
        if depth is None:
            return self._history
        depth = min(depth, len(self._history))
        return self._history[-depth:]


class WindSpeedHistory(History):
    def cms_to_kmph(self, cms):
        return (cms * 60 * 60) / 1000.0 / 100.0

    def latest_kmph(self):
        return self.cms_to_kmph(self.latest().value)

    def average_kmph(self, sample_over=None):
        return self.cms_to_kmph(self.average(sample_over))

    def cms_to_mph(self, cms):
        return ((cms * 60 * 60) / 1000.0 / 100.0) * 0.621371

    def latest_mph(self):
        return self.cms_to_mph(self.latest().value)

    def average_mph(self, sample_over=None):
        return self.cms_to_mph(self.average(sample_over))

    def gust_mph(self, seconds=3.0):
        cut_off_time = time.time() - seconds
        samples = [entry.value for entry in self.history() if entry.timestamp >= cut_off_time]
        return self.cms_to_mph(max(samples))

    def cms_to_ms(self, cms):
        return (cms * 60 * 60) / 1000.0

    def latest_ms(self):
        return self.cms_to_ms(self.latest().value)

    def average_ms(self, sample_over=None):
        return self.cms_to_ms(self.average(sample_over))

    def gust_ms(self, seconds=3.0):
        cut_off_time = time.time() - seconds
        samples = [entry.value for entry in self.history() if entry.timestamp >= cut_off_time]
        return self.cms_to_ms(max(samples))


class WindDirectionHistory(History):
    def degrees_to_cardinal(self, degrees):
        value, cardinal = min(wind_degrees_to_cardinal.items(), key=lambda item: abs(item[0] - degrees))
        return cardinal

    def average_compass(self, sample_over=None):
        return self.degrees_to_cardinal(self.average(sample_over))

    def latest_compass(self):
        return self.degrees_to_cardinal(self.latest().value)

    def history_compass(self, depth=None):
        return [HistoryEntry(self.degrees_to_cardinal(entry.value), timestamp=entry.timestamp) for entry in self.history(depth)]