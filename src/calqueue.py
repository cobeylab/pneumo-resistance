#!/usr/bin/env pypy

import random
import itertools
import math
import time
import sys
import gc

TOL = 1e-10

class StepList(object):
    def __init__(self):
        self.first = None
        self.last = None
        self.size = 0
    
    def unlink(self, node):
        if node.prev:
            node.prev.next = node.next
        else:
            self.first = node.next
        if node.next:
            node.next.prev = node.prev
        else:
            self.last = node.prev
        node.prev = None
        node.next = None
        self.size -= 1
    
    def insert(self, node, prev, next):
        if prev:
            prev.next = node
        else:
            self.first = node
        if next:
            next.prev = node
        else:
            self.last = node
        node.prev = prev
        node.next = next
        self.size += 1
    
    def find_node(self, obj):
        cur = self.first
        while cur:
            if cur.obj == obj:
                return cur
            cur = cur.next
        return None
    
    def find_insertion_point(self, node):
        cur = self.last
        while cur:
            if cur.t < node.t or cur.t == node.t and cur.i < node.i:
                break
            cur = cur.prev
        if cur:
            return cur, cur.next
        return None, self.first
    
    def add(self, obj, t, i):
        node = Node(obj, t, i)
        prev, next = self.find_insertion_point(node)
        self.insert(node, prev, next)
    
    def get_time(self, obj):
        cur = self.first
        while cur:
            if cur.obj == obj:
                return cur.t
            cur = cur.next
    
    def update(self, obj, t, i):
        node = self.find_node(obj)
        self.unlink(node)
        node.t = t
        node.i = i
        prev, next = self.find_insertion_point(node)
        self.insert(node, prev, next)
    
    def remove(self, obj):
        node = self.find_node(obj)
        self.unlink(node)
    
    def pop(self):
        node = self.first
        self.unlink(node)
        return node.obj, node.t
    
    def peek(self):
        if self.first is None:
            return None, None
        return self.first.obj, self.first.t
    
    def verify(self, t_min, t_max):
        size = 0
        cur = self.first
        while cur:
            size += 1
            
            assert cur.t >= t_min
            assert cur.t < t_max
            
            if cur.next:
                assert cur.next.t > cur.t or cur.next.t == cur.t and cur.next.i > cur.i
            
            cur = cur.next
        assert size == self.size
    
    def __repr__(self):
        list_rep = []
        cur = self.first
        while cur:
            list_rep.append((cur.t, cur.i, cur.obj))
            cur = cur.next
        return str(list_rep)

class Node(object):
    def __init__(self, obj, t, i):
        self.t = t
        self.i = i
        self.obj = obj
        self.next = None
        self.prev = None

class CalendarQueue(object):
    def __init__(self, t_min=0.0, bucket_width=1.0, min_bucket_width=1e-4, n_events_rescale=1000000, n_events_resize=10000000):
        assert bucket_width > min_bucket_width
        
        self.t_min = t_min
        self.t = t_min
        self.bucket_width = bucket_width
        self.min_bucket_width = min_bucket_width
        self.n_events_rescale = n_events_rescale
        self.n_events_resize = n_events_resize
        self.dt_sum = 0.0
        self.n_events = 0
        self.cur_step = 0
        self.cal = []
        self.obj_step_dict = {}
        self.obj_step_offset = 0
        self.counter = itertools.count()
        self.size = 0
    
    def get_time(self, obj):
        step = self.obj_step_dict[obj] - self.obj_step_offset
        return self.cal[step].get_time(obj)
    
    def add(self, obj, t):
        rescaled = False
        if ((self.n_events + 1) % self.n_events_rescale) == 0:
            rescaled = self.rescale()
        if not rescaled and self.cur_step > (len(self.cal) // 2):
            self.resize()
        
        assert obj is not None
        assert obj not in self.obj_step_dict
        
        assert t >= self.t_min
        
        step = int((t - self.t_min) / self.bucket_width)
        assert step >= self.cur_step
        
        self.obj_step_dict[obj] = step + self.obj_step_offset
        self.get_step_list(step).add(obj, t, self.counter.next())
        
        self.size += 1
    
    def get_step_list(self, step):
        while not step < len(self.cal):
            self.cal.append(None)
        
        if self.cal[step] is None:
            self.cal[step] = StepList()
        
        return self.cal[step]
    
    def get_step_list_nocreate(self, step):
        if step < len(self.cal):
            return self.cal[step]
        return None
    
    def remove_if_present(self, obj):
        if obj in self.obj_step_dict:
            self.remove(obj)
    
    def remove(self, obj):
        step = self.obj_step_dict.pop(obj) - self.obj_step_offset
        self.cal[step].remove(obj)
        self.size -= 1
    
    def contains(self, obj):
        return obj in self.obj_step_dict
    
    def __contains__(self, obj):
        return obj in self.obj_step_dict
    
    def update(self, obj, t):
        assert obj in self.obj_step_dict
        old_step = self.obj_step_dict[obj] - self.obj_step_offset
        new_step = self.get_step(t)
        if old_step == new_step:
            self.cal[old_step].update(obj, t, self.counter.next())
        else:
            self.cal[old_step].remove(obj)
            self.get_step_list(new_step).add(obj, t, self.counter.next())
            self.obj_step_dict[obj] = new_step + self.obj_step_offset
    
    def add_or_update(self, obj, t):
        if obj in self.obj_step_dict:
            self.update(obj, t)
        else:
            self.add(obj, t)
    
    def get_step(self, t):
        return int((t - self.t_min) / self.bucket_width)
    
    def peek(self):
        if self.size == 0:
            return None, None
        
        cur_step = self.cur_step
        while True:
            step_list = self.cal[self.cur_step]
            if step_list is not None:
                obj, t = step_list.peek()
                if obj is not None:
                    return obj, t
                cur_step += 1
    
    def pop(self):
        if self.size == 0:
            return None
        
        while True:
            step_list = self.cal[self.cur_step]
            if step_list is None:
                self.cur_step += 1
            elif step_list.size == 0:
                self.cal[self.cur_step] = None
                self.cur_step += 1
            else:
                self.size -= 1
                obj, t = step_list.pop()
                assert t >= self.t
                self.dt_sum += t - self.t
                self.n_events += 1
                self.t = t
                del self.obj_step_dict[obj]
                
                return obj, t
    
    def max_step_size(self):
        max_size = 0
        for step in xrange(self.cur_step, len(self.cal)):
            if self.cal[step] is not None:
                step_size = self.cal[step].size
                if step_size > max_size:
                    max_size = step_size
        return max_size
    
    def get_dt_mean(self):
        if self.n_events == 0:
            return None
        return self.dt_sum / self.n_events
    
    def resize(self):
        if self.cur_step == 0:
            return False
        
        self.cal = self.cal[self.cur_step:]
        self.t_min = self.t_min + self.bucket_width * self.cur_step
        self.obj_step_offset += self.cur_step
        self.cur_step = 0
        return True
    
    def rescale(self):
        target_bucket_width = max(self.get_dt_mean() * 2.0, self.min_bucket_width)

        self.dt_sum = 0.0
        self.n_events = 0

        if target_bucket_width > 0.5 * self.bucket_width and target_bucket_width < 2.0 * self.bucket_width:
            return False
        
        old_cal = self.cal
        self.bucket_width = target_bucket_width
        self.t_min = self.t
        self.cur_step = 0
        self.cal = []
        self.obj_step_dict = {}
        self.obj_step_offset = 0
        self.counter = itertools.count()
        self.size = 0
    
        for i in xrange(len(old_cal)):
            step_list = old_cal[i]
            if step_list is not None:
                cur = step_list.first
                while cur:
                    self.add(cur.obj, cur.t)
                    cur = cur.next
            del step_list
            old_cal[i] = None
        del old_cal
        
        return True
    
    def verify(self):
        size = 0
        for i, step_list in enumerate(self.cal):
            if i < self.cur_step:
                assert step_list is None
            else:
                if step_list is not None:
                    t_min = self.t_min + self.bucket_width * i - TOL
                    t_max = self.t_min + self.bucket_width * (i + 1) + TOL
                    size += step_list.size
                    step_list.verify(t_min, t_max)
        assert self.size == size

if __name__ == '__main__':
    cq = CalendarQueue()
    
    t = 0.0
    present = set()
    for i in xrange(100000):
        if cq.size == 0 or random.random() < 0.25:
            cq.add(i, t + random.uniform(0.0, 40.0))
            present.add(i)
        elif random.random() < 0.5:
            for j in present:
                tnew = t + random.uniform(0.0, 40.0)
                print 'updating', j, tnew
                cq.update(j, tnew)
                break
        elif random.random() < 0.5:
            for j in present:
                print 'removing', j
                cq.remove(j)
                present.remove(j)
                break
        else:
            obj, t = cq.pop()
            print 'popped', obj, t
            present.remove(obj)
    print cq.size
    cq.verify()
