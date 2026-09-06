"""Ordered buffer independent of Blender and HTTP completion order."""


class ClipBuffer:
    def __init__(self, prefill=2):
        self.prefill = prefill
        self.next_index = 0
        self.ready = {}
        self.started = False

    def put(self, index, clip):
        if index < self.next_index or index in self.ready:
            raise ValueError("Duplicate or already played clip")
        self.ready[index] = clip

    def pop(self, final=False):
        if not self.started:
            contiguous = 0
            while self.next_index + contiguous in self.ready:
                contiguous += 1
            if contiguous < self.prefill and not (final and contiguous):
                return None
        if self.next_index not in self.ready:
            return None
        clip = self.ready.pop(self.next_index)
        self.next_index += 1
        self.started = True
        return clip

    def __len__(self):
        return len(self.ready)
