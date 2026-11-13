"""Print the effective power overlay GUID via powrprof (read-only API)."""
import ctypes
import uuid


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]


g = GUID()
rc = ctypes.WinDLL("powrprof").PowerGetEffectiveOverlayScheme(ctypes.byref(g))
print(str(uuid.UUID(bytes_le=ctypes.string_at(ctypes.byref(g), 16))) if rc == 0 else f"ERROR rc={rc}")
