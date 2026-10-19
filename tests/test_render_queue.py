import asyncio
import threading
import time
import unittest

from chiko.cartography.render_queue import RenderQueue,RenderBusy


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_simultaneous_requests_share_work_and_bounded_batches(self):
        queue=RenderQueue(budget_seconds=1,cycle_seconds=.005)
        calls=[]
        def image(key):calls.append(key);return str(key).encode()
        try:
            images=await asyncio.gather(*(queue.request(k,lambda k=k:image(k)) for k in [0,0,1,2,3,4,5]))
            self.assertEqual([0,1,2,3,4,5],calls)
            self.assertEqual(images[0],images[1])
            self.assertEqual(2,queue.batches)
            self.assertEqual(6,queue.completed)
            again=await queue.request(0,lambda:None)
            self.assertEqual(images[0],again)
            self.assertEqual(1,queue.hits)
        finally:await queue.aclose()

    async def test_slow_images_yield_and_stop_batch_at_soft_budget(self):
        queue=RenderQueue(budget_seconds=.001,cycle_seconds=.03)
        beats=0
        def image():time.sleep(.025);return b'png'
        async def heartbeat():
            nonlocal beats
            for _ in range(10):beats+=1;await asyncio.sleep(.003)
        try:
            await asyncio.gather(queue.request(1,image),queue.request(2,image),heartbeat())
            self.assertEqual(2,queue.batches)
            self.assertEqual(1,queue.last_batch)
            self.assertEqual(10,beats)
        finally:await queue.aclose()

    async def test_progressive_delivery_and_shutdown_wait_for_active_read(self):
        queue=RenderQueue(budget_seconds=1,cycle_seconds=.001)
        gate=threading.Event();started=threading.Event()
        def second():started.set();gate.wait(2);return b'second'
        first=asyncio.create_task(queue.request(1,lambda:b'first'))
        other=asyncio.create_task(queue.request(2,second))
        try:
            self.assertEqual(b'first',(await asyncio.wait_for(first,1)).data)
            for _ in range(100):
                if started.is_set():break
                await asyncio.sleep(.005)
            self.assertTrue(started.is_set())
            closing=asyncio.create_task(queue.aclose());await asyncio.sleep(.01)
            self.assertFalse(closing.done())
            gate.set();await asyncio.wait_for(closing,1)
            self.assertEqual({},queue.cache)
        finally:
            gate.set();await queue.aclose();await asyncio.gather(first,other,return_exceptions=True)

    async def test_cancelled_waiter_does_not_cancel_other_client(self):
        queue=RenderQueue();gate=threading.Event()
        def image():gate.wait(2);return b'png'
        one=asyncio.create_task(queue.request(1,image));two=asyncio.create_task(queue.request(1,image))
        try:
            await asyncio.sleep(.01);one.cancel();await asyncio.gather(one,return_exceptions=True)
            gate.set();self.assertEqual(b'png',(await asyncio.wait_for(two,1)).data)
            self.assertEqual(1,queue.completed)
        finally:gate.set();await queue.aclose()

    async def test_queue_capacity_cache_quota_and_changed_input(self):
        queue=RenderQueue(max_pending=1,max_bytes=10,max_entries=2,cycle_seconds=.001)
        gate=threading.Event()
        first=asyncio.create_task(queue.request(1,lambda:(gate.wait(2),b'123456')[1]))
        try:
            await asyncio.sleep(.01)
            with self.assertRaises(RenderBusy):await queue.request(2,lambda:b'abcdef')
            gate.set();await first
            await queue.request(2,lambda:b'abcdef')
            self.assertLessEqual(queue.bytes,10);self.assertNotIn(1,queue.cache)
            await queue.request(3,lambda:b'changed',valid=lambda:False)
            self.assertNotIn(3,queue.cache)
        finally:gate.set();await queue.aclose()

    async def test_renderer_error_does_not_stop_following_request(self):
        queue=RenderQueue(cycle_seconds=.001)
        def error():raise LookupError('missing')
        try:
            with self.assertRaises(LookupError):await queue.request(1,error)
            self.assertEqual(b'ok',(await queue.request(2,lambda:b'ok')).data)
            self.assertEqual(1,queue.failed)
        finally:await queue.aclose()
