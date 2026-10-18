"""Incrementally reads explicitly selected Content Log; no game files are modified."""
import json
from pathlib import Path

PREFIX = '[BEDROCK_LIVE_MAP]'


class ContentLog:
    def __init__(self, filename):
        self.path = Path(filename)
        self.offset = 0
        self.pending = b''
        self.stamp = None

    def read(self):
        packets=self.read_packets()
        players=[packet['players'] for packet in packets if isinstance(packet.get('players'),list)]
        return players[-1] if players else None

    def read_packets(self):
        if not self.path.is_file():
            return []
        stat = self.path.stat()
        if self.stamp is None:
            # Never replay historical positions: start at current end of log.
            self.offset = stat.st_size
            self.stamp = stat.st_ctime_ns
            return []
        if stat.st_size < self.offset or self.stamp != stat.st_ctime_ns:
            self.offset, self.pending = 0, b''
            self.stamp = stat.st_ctime_ns
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            data = stream.read(1024*1024)
            self.offset = stream.tell()
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        if len(self.pending)>1024*1024:
            self.pending=b''
        result = []
        for line in lines:
            text = line.decode('utf-8', errors='replace')
            if PREFIX not in text:
                continue
            try:
                packet, _ = json.JSONDecoder().raw_decode(text.split(PREFIX,1)[1].strip())
                if isinstance(packet,dict):
                    result.append(packet)
            except (ValueError,AttributeError):
                pass
        return result
