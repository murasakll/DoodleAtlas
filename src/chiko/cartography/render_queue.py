"""Bounded on-demand rendering for existing tiles. No world or disk-cache writes."""
import asyncio
import hashlib
import os
import time
from collections import OrderedDict
from dataclasses import dataclass


class RenderBusy(RuntimeError):
    pass


class RenderClosed(RuntimeError):
    pass


@dataclass(frozen=True)
class Rendered:
    data: bytes
    etag: str


def background_call(function):
    """Lower only this rendering thread's priority, then restore it before reuse."""
    restore=None
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentThread.restype=wintypes.HANDLE
        kernel.GetThreadPriority.argtypes=[wintypes.HANDLE]
        kernel.SetThreadPriority.argtypes=[wintypes.HANDLE,ctypes.c_int]
        thread=kernel.GetCurrentThread(); original=kernel.GetThreadPriority(thread)
        if original!=0x7fffffff and kernel.SetThreadPriority(thread,-1):
            restore=lambda:kernel.SetThreadPriority(thread,original)
    try:
        return function(),restore is not None
    finally:
        if restore:restore()


class RenderQueue:
    def __init__(self,batch_size=4,budget_seconds=.008,cycle_seconds=.05,
                 max_pending=128,max_bytes=16*1024*1024,max_entries=512):
        if batch_size<1 or budget_seconds<=0 or cycle_seconds<=0 or max_pending<1 or max_bytes<1 or max_entries<1:
            raise ValueError('Limites da fila devem ser positivos')
        self.batch_size=batch_size;self.budget=budget_seconds;self.cycle=cycle_seconds
        self.max_pending=max_pending;self.max_bytes=max_bytes;self.max_entries=max_entries
        self.cache=OrderedDict();self.bytes=0;self.pending=OrderedDict();self.running=0
        self.task=None;self.closed=False;self.wake=asyncio.Event()
        self.completed=0;self.failed=0;self.hits=0;self.batches=0
        self.last_batch=0;self.last_wall=0.;self.max_wall=0.;self.priority_lowered=False

    async def request(self,key,render,valid=lambda:True):
        if self.closed:raise RenderClosed('Fila encerrada')
        cached=self.cache.get(key)
        if cached is not None:
            self.cache.move_to_end(key);self.hits+=1;return cached
        job=self.pending.get(key)
        if job is None:
            if len(self.pending)>=self.max_pending:raise RenderBusy('Fila de imagens cheia')
            job={'future':asyncio.get_running_loop().create_future(),'render':render,'valid':valid,'waiters':0,'started':False}
            self.pending[key]=job
        job['waiters']+=1
        if self.task is None or self.task.done():self.task=asyncio.create_task(self._run())
        try:
            return await asyncio.shield(job['future'])
        finally:
            job['waiters']-=1
            if not job['waiters'] and not job['started'] and self.pending.get(key) is job:
                self.pending.pop(key);job['future'].cancel()
            elif not job['waiters'] and job['started']:
                # A disconnected client must not leave an unobserved exception.
                job['future'].add_done_callback(lambda f:None if f.cancelled() else f.exception())

    async def _run(self):
        # Let simultaneous HTTP requests join the first batch without waiting a cycle.
        await asyncio.sleep(0)
        while self.pending and not self.closed:
            start=time.perf_counter();processed=0
            for key in list(self.pending)[:self.batch_size]:
                job=self.pending.get(key)
                if job is None:continue
                if self.closed:break
                job['started']=True;self.running=1
                try:
                    data,lowered=await asyncio.to_thread(background_call,job['render'])
                    self.priority_lowered=lowered
                    result=Rendered(data,'"'+hashlib.sha256(data).hexdigest()+'"')
                    if not self.closed and job['valid']() and len(data)<=self.max_bytes:
                        old=self.cache.pop(key,None)
                        if old:self.bytes-=len(old.data)
                        self.cache[key]=result;self.bytes+=len(data)
                        while self.bytes>self.max_bytes or len(self.cache)>self.max_entries:
                            _,old=self.cache.popitem(last=False);self.bytes-=len(old.data)
                    self.completed+=1
                    if not job['future'].done():
                        if self.closed:job['future'].set_exception(RenderClosed('Fila encerrada'))
                        else:job['future'].set_result(result)
                except Exception as error:
                    self.failed+=1
                    if not job['future'].done():job['future'].set_exception(error)
                finally:
                    self.running=0;self.pending.pop(key,None);processed+=1
                if time.perf_counter()-start>=self.budget:break
            self.batches+=1;self.last_batch=processed;self.last_wall=time.perf_counter()-start;self.max_wall=max(self.max_wall,self.last_wall)
            if self.pending and not self.closed:
                # Soft budget: native work cannot be preempted midway through an image.
                try:await asyncio.wait_for(self.wake.wait(),timeout=max(.01,self.cycle-self.last_wall))
                except asyncio.TimeoutError:pass

    async def aclose(self):
        self.closed=True;self.wake.set()
        for key,job in list(self.pending.items()):
            if not job['started']:
                self.pending.pop(key,None)
                if not job['future'].done():job['future'].set_exception(RenderClosed('Fila encerrada'))
        # Finish the one active read before the caller removes a temporary session.
        if self.task:await asyncio.gather(self.task,return_exceptions=True)
        self.cache.clear();self.bytes=0

    def stats(self):
        return {'queued':max(0,len(self.pending)-self.running),'running':self.running,
                'cache_entries':len(self.cache),'cache_bytes':self.bytes,'cache_hits':self.hits,
                'completed':self.completed,'failed':self.failed,'batches':self.batches,
                'batch_limit':self.batch_size,'last_batch':self.last_batch,
                'budget_ms':round(self.budget*1000,2),'cycle_ms':round(self.cycle*1000,2),
                'last_batch_wall_ms':round(self.last_wall*1000,3),'max_batch_wall_ms':round(self.max_wall*1000,3),
                'priority_lowered':self.priority_lowered}
