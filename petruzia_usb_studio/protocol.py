"""ZMK Studio protobuf RPC over framed CDC ACM serial, not HID/VIA."""
import queue
import threading
import time

import serial
from google.protobuf.message import DecodeError
import studio_pb2 as studio
import meta_pb2 as meta
import keymap_pb2 as keymap

SOF, ESC, EOF = 0xAB, 0xAC, 0xAD


def frame(payload):
    out = bytearray([SOF])
    for b in payload:
        if b in (SOF, ESC, EOF):
            out.append(ESC)
        out.append(b)
    out.append(EOF)
    return bytes(out)


class FrameDecoder:
    def __init__(self, limit=1024 * 1024):
        self.state = 0
        self.data = bytearray()
        self.limit = limit

    def feed(self, chunk):
        result = []
        for b in chunk:
            if self.state == 0:
                if b == SOF:
                    self.data.clear()
                    self.state = 1
            elif self.state == 2:
                self.data.append(b)
                self.state = 1
            elif b == SOF:
                self.data.clear()
            elif b == ESC:
                self.state = 2
            elif b == EOF:
                result.append(bytes(self.data))
                self.data.clear()
                self.state = 0
            else:
                self.data.append(b)
            if len(self.data) > self.limit:
                self.data.clear()
                self.state = 0
                raise ValueError('RPC frame exceeds safety limit')
        return result


class RpcError(RuntimeError):
    pass


class LockedError(RpcError):
    pass


class StudioClient:
    def __init__(self, port=None, transport=None):
        self.serial = transport or serial.Serial(port, baudrate=12500, timeout=0.1, write_timeout=3)
        self.events = queue.Queue()
        self.pending = {}
        self.guard = threading.Lock()
        self.calls = threading.Lock()
        self.counter = 0
        self.closed = False
        self.failure = None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        decoder = FrameDecoder()
        try:
            while not self.closed:
                data = self.serial.read(min(max(self.serial.in_waiting, 1), 4096))
                for payload in decoder.feed(data):
                    try:
                        msg = studio.Response.FromString(payload)
                    except DecodeError as exc:
                        raise RpcError('Malformed protobuf response') from exc
                    if msg.WhichOneof('type') == 'notification':
                        self.events.put(('notification', msg.notification))
                    elif msg.WhichOneof('type') == 'request_response':
                        response = msg.request_response
                        with self.guard:
                            target = self.pending.get(response.request_id)
                        if target is not None:
                            target.put(response)
        except Exception as exc:
            if not self.closed:
                self.failure = str(exc)
                self.events.put(('disconnected', str(exc)))
                with self.guard:
                    for target in self.pending.values():
                        target.put(RpcError('USB connection lost: ' + str(exc)))

    def call(self, subsystem, method, value=True, timeout=7):
        with self.calls:
            if self.closed or self.failure:
                raise RpcError(self.failure or 'Not connected')
            self.counter = (self.counter % 0xFFFFFFFF) + 1
            request = studio.Request(request_id=self.counter)
            part = getattr(request, subsystem)
            field = getattr(part, method)
            if hasattr(field, 'CopyFrom'):
                field.CopyFrom(value)
            else:
                setattr(part, method, value)
            target = queue.Queue()
            with self.guard:
                self.pending[self.counter] = target
            try:
                wire = frame(request.SerializeToString())
                written = self.serial.write(wire)
                if written != len(wire):
                    raise RpcError('Incomplete USB write; outcome unknown. Read back before retrying.')
                try:
                    response = target.get(timeout=timeout)
                except queue.Empty as exc:
                    raise RpcError('No matching ZMK Studio response. Check Studio firmware, USB output, and port. For a write, outcome is UNKNOWN: read back before retrying.') from exc
                if isinstance(response, Exception):
                    raise response
                if response.WhichOneof('subsystem') == 'meta':
                    if response.meta.WhichOneof('response_type') == 'simple_error':
                        code = response.meta.simple_error
                        if code == meta.UNLOCK_REQUIRED:
                            raise LockedError('Board is locked. Press its physical &studio_unlock key, then Read keyboard.')
                        raise RpcError('Device RPC error: ' + meta.ErrorConditions.Name(code))
                    raise RpcError('Device returned no_response instead of requested data')
                if response.WhichOneof('subsystem') != subsystem:
                    raise RpcError('Unexpected RPC subsystem')
                answer = getattr(response, subsystem)
                if answer.WhichOneof('response_type') != method:
                    raise RpcError('Unexpected RPC response type')
                return getattr(answer, method)
            finally:
                with self.guard:
                    self.pending.pop(request.request_id, None)

    def set_binding(self, layer_id, position, binding):
        result = self.call('keymap', 'set_layer_binding', keymap.SetLayerBindingRequest(
            layer_id=layer_id, key_position=position, binding=binding))
        if result != keymap.SET_LAYER_BINDING_RESP_OK:
            raise RpcError(keymap.SetLayerBindingResponse.Name(result))

    def save(self):
        result = self.call('keymap', 'save_changes')
        if result.WhichOneof('result') != 'ok' or not result.ok:
            detail = keymap.SaveChangesErrorCode.Name(result.err) if result.WhichOneof('result') == 'err' else 'missing success'
            raise RpcError('Save failed: ' + detail)

    def close(self):
        self.closed = True
        self.serial.close()
        if threading.current_thread() is not self.reader:
            self.reader.join(timeout=1)
