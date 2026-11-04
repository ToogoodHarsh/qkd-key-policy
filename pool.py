"""The key tank. Bookkeeping after Zheng Eq. (1): new stock = stock + generated - used."""


class KeyPool:
    def __init__(self, capacity, stock):
        self.capacity = capacity
        self.initial = float(stock)
        self.stock = float(stock)
        self.generated = 0.0
        self.wasted = 0.0                 # keys lost because the tank was full
        self.used = {"otp": 0.0, "aes": 0.0, "shared": 0.0}
        self.min_stock = self.stock

    def add(self, bits):
        self.generated += bits
        self.stock += bits
        if self.stock > self.capacity:
            self.wasted += self.stock - self.capacity
            self.stock = self.capacity

    def take(self, bits, kind):
        if bits > self.stock + 1e-9:
            raise ValueError("not enough key bits in the tank")
        self.stock -= bits
        self.used[kind] += bits
        self.min_stock = min(self.min_stock, self.stock)

    @property
    def total_used(self):
        return sum(self.used.values())
