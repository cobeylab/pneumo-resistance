import itertools

def get_left(i):
    return 2 * (i + 1) - 1

def get_right(i):
    return 2 * (i + 1)

def get_parent(i):
    return ((i + 1) // 2) - 1

class HeapQueue(object):
    def __init__(self):
        self.heap = []
        self.index = {}
        self.counter = itertools.count()
    
    @property
    def size(self):
        return len(self.heap)
    
    @property
    def next_priority(self):
        return self.heap[0][0]
    
    def get_time(self, obj):
        loc = self.index[obj]
        return self.heap[loc][0]
    
    def add(self, obj, priority):
        assert obj not in self.index
        
        count = self.counter.next()
        loc = len(self.heap)
        self.index[obj] = loc
        self.heap.append((priority, count, obj))
        self.heapify_up(loc)
    
    def add_or_update(self, obj, priority):
        if obj in self.index:
            self.update(obj, priority)
        else:
            self.add(obj, priority)
    
    def remove(self, obj):
        loc = self.index[obj]
        self.remove_at_index(loc)
    
    def remove_if_present(self, obj):
        if obj in self.index:
            self.remove(obj)
    
    def contains(self, obj):
        return obj in self.index
    
    def __contains__(self, obj):
        return obj in self.index
    
    def update(self, obj, priority):
        loc = self.index[obj]
        self.heap[loc] = (priority, self.counter.next(), obj)
        if not self.heapify_down(loc):
            self.heapify_up(loc)
    
    def peek(self):
        priority, count, obj = self.heap[0]
        return obj, priority
    
    def pop(self):
        priority, count, obj = self.heap[0]
        self.remove_at_index(0)
        return obj, priority
    
    def remove_at_index(self, loc):
        entry = self.heap[loc]
        last_loc = len(self.heap) - 1
        if loc < last_loc:
            self.swap(loc, last_loc)
            del self.index[entry[2]]
            del self.heap[-1]
            if not self.heapify_down(loc):
                self.heapify_up(loc)
        else:
            del self.index[entry[2]]
            del self.heap[-1]
        
    
    def swap(self, i1, i2):
        entry1 = self.heap[i1]
        entry2 = self.heap[i2]
        
        self.heap[i1] = entry2
        self.index[entry2[2]] = i1
        
        self.heap[i2] = entry1
        self.index[entry1[2]] = i2
    
    def heapify_down(self, loc):
        size = len(self.heap)
        swapped = False
        left = get_left(loc)
        if left < size:
            right = get_right(loc)
            if self.heap[left][:2] < self.heap[loc][:2]:
                if right < size:
                    if self.heap[left][:2] < self.heap[right][:2]:
                        self.swap(loc, left)
                        self.heapify_down(left)
                        swapped = True
                    else:
                        self.swap(loc, right)
                        self.heapify_down(right)
                        swapped = True
                else:
                    self.swap(loc, left)
                    self.heapify_down(left)
                    swapped = True
            elif right < size and self.heap[right][:2] < self.heap[loc][:2]:
                self.swap(loc, right)
                self.heapify_down(right)
                swapped = True
        return swapped
    
    def heapify_up(self, loc):
        parent = get_parent(loc)
        if parent >= 0 and self.heap[loc][:2] < self.heap[parent][:2]:
            self.swap(parent, loc)
            self.heapify_up(parent)
            return True
        return False
    
    def verify(self):
        heap = self.heap
        size = len(heap)
        for i in range(len(heap)):
            left = get_left(i)
            if left < size:
                if heap[i][:2] > heap[left][:2]:
                    print i, left, 'screwed up', heap[i][:2], heap[left][:2]
                assert heap[i][:2] < heap[left][:2]
            
            right = get_right(i)
            if right < size:
                if heap[i][:2] > heap[right][:2]:
                    print i, right, 'screwed up', heap[i][:2], heap[right][:2]
                assert heap[i][:2] < heap[right][:2]
            
            assert self.index[heap[i][2]] == i
