import unittest
from protocol import frame, FrameDecoder

class FramingTests(unittest.TestCase):
    def test_official_simple_fixture(self):
        self.assertEqual(frame(bytes([1,2,3])), bytes([0xAB,1,2,3,0xAD]))
    def test_official_escape_fixture(self):
        payload=bytes([1,0xAB,0xAC,2,3,0xAB,4,0xAD,5])
        self.assertEqual(frame(payload), bytes([0xAB,1,0xAC,0xAB,0xAC,0xAC,2,3,0xAC,0xAB,4,0xAC,0xAD,5,0xAD]))
    def test_decoder_streaming(self):
        d=FrameDecoder(); wire=frame(b'abc')+frame(bytes([0xAB,0xAC,0xAD]))
        out=[]
        for part in (wire[:2],wire[2:7],wire[7:]): out.extend(d.feed(part))
        self.assertEqual(out,[b'abc',bytes([0xAB,0xAC,0xAD])])
    def test_noise_and_resync(self):
        d=FrameDecoder(); self.assertEqual(d.feed(b'noise'+frame(b'x')), [b'x'])

import queue
import studio_pb2 as studio
import keymap_pb2 as keymap
from protocol import StudioClient, LockedError, RpcError

class SimulatedTransport:
    """Unit-test double only: never used by the application."""
    def __init__(self, reply):
        self.reply=reply; self.rx=queue.Queue(); self.requests=[]
    @property
    def in_waiting(self): return self.rx.qsize()
    def read(self, count):
        try: return bytes([self.rx.get(timeout=.01)])
        except queue.Empty: return b''
    def write(self, wire):
        request=studio.Request.FromString(FrameDecoder().feed(wire)[0]); self.requests.append(request)
        for response in self.reply(request):
            for b in frame(response.SerializeToString()): self.rx.put(b)
        return len(wire)
    def close(self): pass

class RpcTests(unittest.TestCase):
    def test_request_schema_and_wire(self):
        req=studio.Request(request_id=1); req.core.get_device_info=True
        self.assertEqual(req.SerializeToString(), bytes.fromhex('08011a020801'))
        req=studio.Request(request_id=1)
        req.keymap.set_layer_binding.CopyFrom(keymap.SetLayerBindingRequest(layer_id=2,key_position=3,binding=keymap.BehaviorBinding(behavior_id=5,param1=0x70004)))
        self.assertEqual(req.keymap.set_layer_binding.binding.SerializeToString(),bytes.fromhex('080a1084801c'))
    def test_match_id_and_notifications(self):
        def reply(req):
            wrong=studio.Response(); wrong.request_response.request_id=req.request_id+1; wrong.request_response.core.get_lock_state=0
            event=studio.Response(); event.notification.core.lock_state_changed=1
            good=studio.Response(); good.request_response.request_id=req.request_id; good.request_response.core.get_lock_state=1
            return [wrong,event,good]
        c=StudioClient(transport=SimulatedTransport(reply))
        try:
            self.assertEqual(c.call('core','get_lock_state'),1)
            self.assertEqual(c.events.get(timeout=1)[1].core.lock_state_changed,1)
        finally: c.close()
    def test_locked_error(self):
        def reply(req):
            r=studio.Response(); r.request_response.request_id=req.request_id; r.request_response.meta.simple_error=1; return [r]
        c=StudioClient(transport=SimulatedTransport(reply))
        try:
            with self.assertRaises(LockedError): c.call('keymap','get_keymap')
        finally: c.close()
    def test_set_binding_rejected_and_save_failure(self):
        def reply(req):
            r=studio.Response(); r.request_response.request_id=req.request_id
            if req.keymap.WhichOneof('request_type')=='set_layer_binding': r.request_response.keymap.set_layer_binding=3
            else: r.request_response.keymap.save_changes.err=3
            return [r]
        c=StudioClient(transport=SimulatedTransport(reply))
        try:
            with self.assertRaisesRegex(RpcError,'INVALID_PARAMETERS'): c.set_binding(7,2,keymap.BehaviorBinding(behavior_id=5,param1=3))
            with self.assertRaisesRegex(RpcError,'NO_SPACE'): c.save()
        finally: c.close()
    def test_timeout_never_success(self):
        c=StudioClient(transport=SimulatedTransport(lambda req: []))
        try:
            with self.assertRaisesRegex(RpcError,'UNKNOWN'): c.call('keymap','save_changes',timeout=.02)
        finally: c.close()

if __name__ == '__main__': unittest.main()
