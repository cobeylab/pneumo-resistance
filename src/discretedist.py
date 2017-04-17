#!/usr/bin/env pypy

import numpy

class DiscreteDistribution(object):
    def __init__(self, rng, pdf, bin_size=None):
        self.rng = rng
        self.pdf = numpy.array(pdf)
        
        if bin_size is None:
            bin_size = self.pdf.min()
        bin_size = float(bin_size)
        
        bins_per_index = numpy.array(numpy.ceil(self.pdf / bin_size), dtype=numpy.uint32)
        
        self.p_accept = self.pdf / (bins_per_index * bin_size)
        
        n_bins = int(bins_per_index.sum())
        self.table = numpy.zeros(n_bins, dtype=numpy.uint32)
        table_index = 0
        for i in range(self.pdf.shape[0]):
            self.table[table_index:table_index + bins_per_index[i]] = i
            table_index += bins_per_index[i]
    
    def next_discrete(self):
        while True:
            value = self.table[self.rng.random_integers(0, self.table.shape[0] - 1)]
            if self.rng.rand() < self.p_accept[value]:
                return value
    
    def next_continuous(self):
        return self.next_discrete() + self.rng.rand()
