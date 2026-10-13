"""Thai word breaking with Windows' own Uniscribe dictionary (usp10.dll ScriptBreak) - no third-party packages.
breaks(text) -> text with '|' inserted at every soft-break position inside Thai runs (existing '|', spaces, '*' kept)."""
import ctypes, ctypes.wintypes as W
usp = ctypes.WinDLL('usp10')
class SCRIPT_ANALYSIS(ctypes.Structure): _fields_ = [('bits', ctypes.c_uint16), ('state', ctypes.c_uint16)]
class SCRIPT_ITEM(ctypes.Structure): _fields_ = [('iCharPos', ctypes.c_int), ('a', SCRIPT_ANALYSIS)]
def _soft(text):
    """set of indices i where a line may break before text[i]"""
    n = len(text); items = (SCRIPT_ITEM * (n + 1))(); cnt = ctypes.c_int()
    assert usp.ScriptItemize(ctypes.c_wchar_p(text), n, n + 1, None, None, items, ctypes.byref(cnt)) == 0
    out = set()
    for k in range(cnt.value):
        a, b = items[k].iCharPos, items[k + 1].iCharPos; la = (ctypes.c_uint8 * (b - a))()
        assert usp.ScriptBreak(ctypes.c_wchar_p(text[a:b]), b - a, ctypes.byref(items[k].a), la) == 0
        out |= {a + j for j in range(1, b - a) if la[j] & 1}          # fSoftBreak = bit 0
    return out
def breaks(text):
    if not text: return text
    s = _soft(text); th = lambda c: '\u0e00' <= c <= '\u0e7f'
    return ''.join(('|' if i in s and th(c) and th(text[i - 1]) else '') + c for i, c in enumerate(text))
if __name__ == '__main__':
    r = breaks('ถึงแม้ชาวเมืองจะต้องทนทุกข์ทรมานจากโรคระบาด แต่ตราบใดที่ท่านยังอยู่'); print(r)
    assert r.replace('|', '') == 'ถึงแม้ชาวเมืองจะต้องทนทุกข์ทรมานจากโรคระบาด แต่ตราบใดที่ท่านยังอยู่' and r.count('|') >= 8
    assert 'ทุ|กข์' not in r and 'เ|มือง' not in r                       # never splits inside a syllable cluster
