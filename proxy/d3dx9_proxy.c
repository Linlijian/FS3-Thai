/*
 * d3dx9_25.dll proxy for Fantasia Sango 3 -- diagnostic + charset override.
 *
 * FS3.exe is wrapped in Steam DRM (.bind section, .text entropy 8.00), so the
 * charset it passes to D3DXCreateFontA cannot be read statically. This proxy
 * logs the real arguments and can rewrite the charset before forwarding.
 *
 * The first version hooked TextOutA in the executable's import table only, and
 * never fired once. The reason: D3DXFont rasterises glyphs inside
 * d3dx9_25_orig.dll, which imports ExtTextOutA/W, GetGlyphOutlineA/W and
 * MultiByteToWideChar -- and no TextOutA at all. The game's own TextOutA import
 * belongs to some other path the dialogue never takes.
 *
 * So this version hooks the calls that actually carry the text, and patches the
 * import table of EVERY loaded module rather than just the executable.
 * MultiByteToWideChar is the most informative of them: it shows the engine's
 * raw bytes together with the codepage D3DX derived from the charset, which is
 * where the Big5->GBK question (Bin/Code/b2g.dat) gets settled.
 *
 * Every export except D3DXCreateFontA is forwarded by the .def file.
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <intrin.h>

#if defined(_WIN64)
#error "FS3.exe is PE32/i386 -- this proxy must be built 32-bit. Use the x86 Native Tools prompt (MSVC) or the i686 toolchain (MinGW)."
#endif

#ifdef _MSC_VER
/* MSVC gets its export table from linker pragmas rather than the .def.
   link.exe rejects a forwarder that also carries an explicit @ordinal, which
   is what made every forwarded name come back as LNK2001. The pragma form has
   no such restriction. The .def is still shipped, for MinGW. */
#include "exports_msvc.h"
#endif

#define CFG_FILE  "FS3_TH_hook.ini"
#define LOG_FILE  "FS3_TH_hook.log"
#define MAP_FILE  "FS3_TH_map.txt"

static HMODULE g_orig;
static FILE   *g_log;
static int     g_force_charset = 222;   /* THAI_CHARSET; -1 disables */
static char    g_force_face[64];        /* empty = leave the face alone */
static int     g_log_textout = 1;
static int     g_log_mb2wc = 1;
static int     g_hooked_textout;
static int     g_log_draw = 1;          /* log ID3DXFont::DrawTextA/W (step E, black-box) */
static int     g_thai_layout, g_thai_scale, g_thai_dy, g_thai_charset, g_engine_glyphs, g_wrap_w, g_pitch_pct, g_box_lines;   /* defined with defaults in the Thai layout block */
static char    g_thai_face[64];
static HMODULE g_self;
static char    g_dir[MAX_PATH];         /* folder this DLL sits in */
static char    g_ini[MAX_PATH];         /* absolute path to the ini */

typedef HRESULT (WINAPI *PFN_CreateFontA)(void *, INT, UINT, UINT, UINT, BOOL,
                                          DWORD, DWORD, DWORD, DWORD,
                                          LPCSTR, void **);
/* The text never reaches GDI through the game's own TextOutA. D3DXFont
   rasterises glyphs inside d3dx9_25_orig.dll, which imports ExtTextOutA/W,
   GetGlyphOutlineA/W and MultiByteToWideChar -- and no TextOutA at all. The
   first hook attempt patched only the EXE's import table, so it could never
   have fired. These are the calls that actually carry the text. */
typedef BOOL (WINAPI *PFN_TextOutA)(HDC, int, int, LPCSTR, int);
typedef BOOL (WINAPI *PFN_TextOutW)(HDC, int, int, LPCWSTR, int);
typedef BOOL (WINAPI *PFN_ExtTextOutA)(HDC, int, int, UINT, const RECT *,
                                       LPCSTR, UINT, const INT *);
typedef BOOL (WINAPI *PFN_ExtTextOutW)(HDC, int, int, UINT, const RECT *,
                                       LPCWSTR, UINT, const INT *);
typedef int (WINAPI *PFN_MB2WC)(UINT, DWORD, LPCCH, int, LPWSTR, int);

static PFN_TextOutA    g_real_textout;
static PFN_TextOutW    g_real_textoutw;
static PFN_ExtTextOutA g_real_exttextouta;
static PFN_ExtTextOutW g_real_exttextoutw;
static PFN_MB2WC       g_real_mb2wc;

static int g_lines;                 /* log line budget, keeps the file sane */
static int g_max_lines = 4000;

/* Named hooklog, not logf -- logf() is the float logarithm in math.h. */
static void install_hooks(void);
static void load_wrap_rules(const char *v);
static unsigned long long fnv(unsigned long long h, const void *p, int n);
static int first_time(unsigned long long h);

static void hooklog(const char *fmt, ...)
{
    va_list ap;
    if (!g_log) return;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fflush(g_log);                 /* flushed per line: a crash still leaves a
                                      complete log up to the last call */
    if (++g_lines == g_max_lines)
        fprintf(g_log, "=== log_max_lines reached, further text calls are "
                       "no longer logged ===\n");
}

static void log_bytes(const char *tag, const unsigned char *p, int n)
{
    char hex[3 * 64 + 8];
    char asc[64 + 8];
    int i, h = 0, a = 0;
    if (n > 64) n = 64;
    for (i = 0; i < n; i++) {
        h += sprintf(hex + h, "%02x ", p[i]);
        asc[a++] = (p[i] >= 0x20 && p[i] < 0x7f) ? (char)p[i] : '.';
    }
    hex[h] = 0;
    asc[a] = 0;
    hooklog("    %s len=%d hex=%s| ascii=%s", tag, n, hex, asc);
}

/* ---------------------------------------------------------------- config */

static void load_config(void)
{
    char v[512];
    /* GetPrivateProfileString resolves a bare filename against the Windows
       directory, so the path has to be absolute. Defaults = the in-game tested FS3_TH_hook.ini, so a missing ini is
       harmless (plana-a28: no ini -> old PoC defaults, charset 222 crashed on the first Thai mark and disabled Thai). */
    if (GetPrivateProfileStringA("hook", "force_charset", "-1",
                                 v, sizeof v, g_ini) > 0)
        g_force_charset = atoi(v);
    GetPrivateProfileStringA("hook", "force_face", "",
                             g_force_face, sizeof g_force_face, g_ini);
    g_log_textout = GetPrivateProfileIntA("hook", "log_textout", 0, g_ini);
    g_log_mb2wc = GetPrivateProfileIntA("hook", "log_mb2wc", 0, g_ini);
    g_max_lines = GetPrivateProfileIntA("hook", "log_max_lines", 200000, g_ini);
    g_log_draw = GetPrivateProfileIntA("hook", "log_drawtext", 0, g_ini);
    g_thai_layout = GetPrivateProfileIntA("hook", "thai_layout", 1, g_ini);
    GetPrivateProfileStringA("hook", "thai_face", "", g_thai_face, sizeof g_thai_face, g_ini);
    g_thai_scale = GetPrivateProfileIntA("hook", "thai_scale_pct", 155, g_ini);
    g_thai_dy = GetPrivateProfileIntA("hook", "thai_dy", 999, g_ini);
    g_thai_charset = GetPrivateProfileIntA("hook", "thai_charset", 1, g_ini);
    g_engine_glyphs = GetPrivateProfileIntA("hook", "thai_use_engine_font", 0, g_ini);
    g_wrap_w = GetPrivateProfileIntA("hook", "wrap_width", 580, g_ini);
    g_pitch_pct = GetPrivateProfileIntA("hook", "line_pitch_pct", 90, g_ini);
    g_box_lines = GetPrivateProfileIntA("hook", "box_lines", 0, g_ini);
    GetPrivateProfileStringA("hook", "wrap_rules", "16@288:330=300/e,16@328:363=300/e,20@294:70=300/e,20@294:98=300/e,20@294:126=300/e,20@294:154=300/e,20@294:182=300/e,24@55=300/e,20@32:209=300/e,20@>240:104=300/e,24@>440:101=300/e,20@>220:111=300/e,20@>220:139=300/e,20@328=300/e,20@388=300/e,12@689=96,12@673=112,12@662=128,24@>640=130/e,20@>640=135/e,20@260=140/e,12@17=72/e,12@>730:85=62/e,12@0=168", v, sizeof v, g_ini); load_wrap_rules(v);
}

/* Resolve paths next to this DLL rather than the process CWD. */
static void init_paths(HINSTANCE self)
{
    char *slash;
    GetModuleFileNameA(self, g_dir, sizeof g_dir);
    slash = strrchr(g_dir, '\\');
    if (slash) slash[1] = 0; else g_dir[0] = 0;
    _snprintf(g_ini, sizeof g_ini, "%s%s", g_dir, CFG_FILE);
    g_ini[sizeof g_ini - 1] = 0;
}

/* ------------------------------------------------------- TextOutA logging */

static void log_wide(const char *tag, const WCHAR *w, int n)
{
    char buf[5 * 48 + 8];           /* "%04x " = 5 chars per unit (3 overflowed on long lines: crash after battle, plana-a17) */
    int i, k = 0;
    if (n > 48) n = 48;
    for (i = 0; i < n; i++)
        k += sprintf(buf + k, "%04x ", (unsigned)w[i]);
    buf[k] = 0;
    hooklog("    %s n=%d utf16=%s", tag, n, buf);
}

static BOOL WINAPI my_TextOutA(HDC dc, int x, int y, LPCSTR s, int n)
{
    if (g_log_textout && s && n > 0 && g_lines < g_max_lines) {
        hooklog("TextOutA x=%d y=%d n=%d charset=%d", x, y, n, GetTextCharset(dc));
        log_bytes("bytes", (const unsigned char *)s, n);
    }
    return g_real_textout(dc, x, y, s, n);
}

static BOOL WINAPI my_TextOutW(HDC dc, int x, int y, LPCWSTR s, int n)
{
    if (g_log_textout && s && n > 0 && g_lines < g_max_lines) {
        hooklog("TextOutW x=%d y=%d charset=%d", x, y, GetTextCharset(dc));
        log_wide("wide", s, n);
    }
    return g_real_textoutw(dc, x, y, s, n);
}

static BOOL WINAPI my_ExtTextOutA(HDC dc, int x, int y, UINT f, const RECT *r,
                                  LPCSTR s, UINT n, const INT *dx)
{
    if (g_log_textout && s && n > 0 && g_lines < g_max_lines) {
        hooklog("ExtTextOutA x=%d y=%d n=%u charset=%d", x, y, n, GetTextCharset(dc));
        log_bytes("bytes", (const unsigned char *)s, (int)n);
    }
    return g_real_exttextouta(dc, x, y, f, r, s, n, dx);
}

static BOOL WINAPI my_ExtTextOutW(HDC dc, int x, int y, UINT f, const RECT *r,
                                  LPCWSTR s, UINT n, const INT *dx)
{
    if (g_log_textout && s && n > 0 && g_lines < g_max_lines) {
        hooklog("ExtTextOutW x=%d y=%d charset=%d", x, y, GetTextCharset(dc));
        log_wide("wide", s, (int)n);
    }
    return g_real_exttextoutw(dc, x, y, f, r, s, n, dx);
}

/* ------------------------------------------------------------ Thai channel */

/* The engine turns its Big5 text into GBK before drawing, using b2g.dat for
   87% of characters and b2u.dat + LCMapStringW for the rest. Giving a Big5
   code a b2g.dat entry forces the first path, so the byte pair that arrives
   here is exactly what the patched table produced -- a value the game itself
   never emits. Those reserved pairs are swapped for Thai codepoints on the way
   to UTF-16, which is what ExtTextOutW then draws.
   0 means "not reserved"; the table is 128 KB, which buys an O(1) lookup. */
static unsigned short *g_map;
static int g_map_count;

static void load_map(void)
{
    char path[MAX_PATH];
    char line[256];
    FILE *f;

    _snprintf(path, sizeof path, "%s%s", g_dir, MAP_FILE);
    path[sizeof path - 1] = 0;
    f = fopen(path, "r");
    if (!f) {
        hooklog("no %s -- Thai channel disabled, logging only", MAP_FILE);
        return;
    }
    g_map = (unsigned short *)calloc(65536, sizeof(unsigned short));
    if (!g_map) { fclose(f); return; }
    while (fgets(line, sizeof line, f)) {
        unsigned pair, uni;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%x %x", &pair, &uni) == 2 && pair < 65536 && uni) {
            g_map[pair] = (unsigned short)uni;
            g_map_count++;
        }
    }
    fclose(f);
    hooklog("Thai channel: %d mappings loaded from %s", g_map_count, MAP_FILE);
}

static int reserved(const unsigned char *p)
{
    return g_map ? g_map[(p[0] << 8) | p[1]] : 0;
}

/* Our own GBK -> UTF-16, used only when a reserved pair is present. Every
   non-reserved run is handed to the real API so ordinary Chinese is untouched. */
static int translate(UINT cp, DWORD flags, const unsigned char *s, int n,
                     LPWSTR dst, int dstlen)
{
    int i = 0, out = 0;
    while (i < n) {
        int thai = (i + 1 < n) ? reserved(s + i) : 0;
        if (thai) {
            if (dstlen) {
                if (out >= dstlen) { SetLastError(ERROR_INSUFFICIENT_BUFFER); return 0; }
                dst[out] = (WCHAR)thai;
            }
            out++;
            i += 2;
            continue;
        }
        {   /* longest run with no reserved pair in it */
            int j = i;
            while (j < n) {
                if ((unsigned char)s[j] < 0x80) { j++; continue; }
                if (j + 1 < n && reserved(s + j)) break;
                j += 2;
            }
            if (j > n) j = n;
            if (j > i) {
                int got = g_real_mb2wc(cp, flags, (LPCCH)(s + i), j - i,
                                       dstlen ? dst + out : NULL,
                                       dstlen ? dstlen - out : 0);
                if (!got && dstlen) return 0;
                out += got;
                i = j;
            } else {
                i++;   /* never stall */
            }
        }
    }
    return out;
}

/* Also the most informative hook: the engine's raw bytes arrive here with the
   codepage D3DX derived from the charset. Only calls carrying a byte >= 0x80
   are logged, which filters out the ASCII housekeeping traffic. */
static int WINAPI my_MultiByteToWideChar(UINT cp, DWORD flags, LPCCH src,
                                         int srclen, LPWSTR dst, int dstlen)
{
    int n, i, high = 0, hit = 0;

    if (!src || srclen == 0)
        return g_real_mb2wc(cp, flags, src, srclen, dst, dstlen);

    n = (srclen < 0) ? (int)strlen(src) + 1 : srclen;
    for (i = 0; i < n; i++)
        if ((unsigned char)src[i] >= 0x80) { high = 1; break; }
    if (high && g_map && cp == 936)
        for (i = 0; i + 1 < n; i++)
            if (reserved((const unsigned char *)src + i)) { hit = 1; break; }

    /* A channel hit is always logged, even with log_mb2wc off. Ordinary text
       traffic fills 4000 lines within the first minutes of play, which is what
       hid the first prototype run; the interesting event has to survive that. Each distinct hit string is logged once
       (menus convert their keys every frame, which filled 200,000 lines in plana-a9). */
    if (high && ((hit && first_time(fnv(1469598103934665603ULL, src, n))) || g_log_mb2wc) && g_lines < g_max_lines) {
        hooklog("MultiByteToWideChar cp=%u flags=%lu len=%d%s",
                cp, (unsigned long)flags, n, hit ? "  [THAI CHANNEL]" : "");
        log_bytes("bytes", (const unsigned char *)src, n);
        if (hit) {
            int m;
            for (m = 0; m + 1 < n; m++) {
                int t = reserved((const unsigned char *)src + m);
                if (t) hooklog("        pair %02x%02x -> U+%04X",
                               (unsigned char)src[m], (unsigned char)src[m + 1], t);
            }
        }
    }
    {   /* log_mb2wc=2: also log what the call RETURNED (step D: how are chars absent from b2g.dat handled?) */
        int r = hit ? translate(cp, flags, (const unsigned char *)src, n, dst, dstlen)
                    : g_real_mb2wc(cp, flags, src, srclen, dst, dstlen);
        if (high && g_log_mb2wc >= 2 && dst && dstlen && r > 0 && g_lines < g_max_lines) {
            log_wide("out", dst, r < dstlen ? r : dstlen);
        }
        return r;
    }
}

/* Replace one imported function pointer in a module's IAT. */
static int patch_iat(HMODULE mod, const char *dll, const char *fn,
                     void *repl, void **out_orig)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)mod;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    DWORD rva;

    if (!mod || dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS *)((BYTE *)mod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT]
              .VirtualAddress;
    if (!rva) return 0;

    for (imp = (IMAGE_IMPORT_DESCRIPTOR *)((BYTE *)mod + rva);
         imp->Name; imp++) {
        const char *name = (const char *)((BYTE *)mod + imp->Name);
        IMAGE_THUNK_DATA *thunk, *orig;
        if (lstrcmpiA(name, dll) != 0) continue;
        thunk = (IMAGE_THUNK_DATA *)((BYTE *)mod + imp->FirstThunk);
        orig  = (IMAGE_THUNK_DATA *)((BYTE *)mod +
                    (imp->OriginalFirstThunk ? imp->OriginalFirstThunk
                                             : imp->FirstThunk));
        for (; orig->u1.AddressOfData; thunk++, orig++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            DWORD prot;
            if (IMAGE_SNAP_BY_ORDINAL(orig->u1.Ordinal)) continue;
            ibn = (IMAGE_IMPORT_BY_NAME *)((BYTE *)mod + orig->u1.AddressOfData);
            if (lstrcmpA((const char *)ibn->Name, fn) != 0) continue;
            if (out_orig) *out_orig = (void *)thunk->u1.Function;
            if (!VirtualProtect(&thunk->u1.Function, sizeof(void *),
                                PAGE_READWRITE, &prot)) return 0;
            thunk->u1.Function = (ULONG_PTR)repl;
            VirtualProtect(&thunk->u1.Function, sizeof(void *), prot, &prot);
            return 1;
        }
    }
    return 0;
}

/* Patch one import across EVERY loaded module, not just the executable.

   This is the fix for the dead first attempt: the text is drawn from inside
   d3dx9_25_orig.dll, so patching only the EXE's import table caught nothing.
   Our own module is skipped so the hooks do not call themselves. */
static int patch_iat_all(const char *dll, const char *fn, void *repl,
                         void **out_orig)
{
    HANDLE snap;
    MODULEENTRY32 me;
    int patched = 0;

    snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE)
        return 0;
    me.dwSize = sizeof me;
    if (Module32First(snap, &me)) {
        do {
            void *prev = NULL;
            if (me.hModule == g_self)
                continue;
            if (patch_iat(me.hModule, dll, fn, repl, &prev)) {
                patched++;
                if (out_orig && !*out_orig)
                    *out_orig = prev;
                hooklog("    hooked %s!%s in %s", dll, fn, me.szModule);
            }
        } while (Module32Next(snap, &me));
    }
    CloseHandle(snap);
    return patched;
}

static void install_hooks(void)
{
    struct { const char *dll, *fn; void *repl; void **orig; } h[] = {
        {"GDI32.dll",    "TextOutA",    (void *)my_TextOutA,    (void **)&g_real_textout},
        {"GDI32.dll",    "TextOutW",    (void *)my_TextOutW,    (void **)&g_real_textoutw},
        {"GDI32.dll",    "ExtTextOutA", (void *)my_ExtTextOutA, (void **)&g_real_exttextouta},
        {"GDI32.dll",    "ExtTextOutW", (void *)my_ExtTextOutW, (void **)&g_real_exttextoutw},
        {"KERNEL32.dll", "MultiByteToWideChar", (void *)my_MultiByteToWideChar,
                                                (void **)&g_real_mb2wc},
    };
    int i;
    hooklog("    installing IAT hooks across all loaded modules");
    for (i = 0; i < (int)(sizeof h / sizeof h[0]); i++) {
        int n = patch_iat_all(h[i].dll, h[i].fn, h[i].repl, h[i].orig);
        if (!n)
            hooklog("    %s!%s : not imported by name anywhere", h[i].dll, h[i].fn);
        else if (!*h[i].orig)
            hooklog("    %s!%s : patched %d module(s) but no original captured",
                    h[i].dll, h[i].fn, n);
    }
    /* A module that imports nothing still needs a callable original. */
    if (!g_real_textout)
        g_real_textout = (PFN_TextOutA)GetProcAddress(
            GetModuleHandleA("gdi32.dll"), "TextOutA");
    if (!g_real_textoutw)
        g_real_textoutw = (PFN_TextOutW)GetProcAddress(
            GetModuleHandleA("gdi32.dll"), "TextOutW");
    if (!g_real_exttextouta)
        g_real_exttextouta = (PFN_ExtTextOutA)GetProcAddress(
            GetModuleHandleA("gdi32.dll"), "ExtTextOutA");
    if (!g_real_exttextoutw)
        g_real_exttextoutw = (PFN_ExtTextOutW)GetProcAddress(
            GetModuleHandleA("gdi32.dll"), "ExtTextOutW");
    if (!g_real_mb2wc)
        g_real_mb2wc = (PFN_MB2WC)GetProcAddress(
            GetModuleHandleA("kernel32.dll"), "MultiByteToWideChar");
}


/* ------------------------------------------------- ID3DXFont::DrawText hook */

/* Step E, black-box: the engine is DRM-wrapped, so instead of reading its code we wrap the DrawText methods of the font
   object WE create in D3DXCreateFontA. Logs the string, the RECT before/after (DT_CALCRECT measuring shows up as a changed
   RECT), the format flags and who called (module+RVA). vtable layout (d3dx9 ID3DXFont): 0-2 IUnknown, 3 GetDevice, 4 GetDescA,
   5 GetDescW, 6/7 GetTextMetricsA/W, 8 GetDC, 9 GetGlyphData, 10 PreloadCharacters, 11 PreloadGlyphs, 12/13 PreloadTextA/W,
   14 DrawTextA, 15 DrawTextW. The layout is verified at runtime (GetDescA must echo our arguments) before anything is patched. */
typedef INT (WINAPI *PFN_DrawTextA)(void *, void *, LPCSTR, INT, LPRECT, DWORD, DWORD);
typedef INT (WINAPI *PFN_DrawTextW)(void *, void *, LPCWSTR, INT, LPRECT, DWORD, DWORD);
typedef HRESULT (WINAPI *PFN_GetDescA)(void *, void *);
typedef struct { INT H; UINT W, Wt, Mip; BOOL It; BYTE Cs, Op, Q, Pf; char Face[32]; } FDESC;   /* D3DXFONT_DESCA */
static PFN_DrawTextA g_real_drawa;
static PFN_DrawTextW g_real_draww;
static void **g_vt_orig, *g_vt_copy[32];
static unsigned long long g_seen[2048];   /* ponytail: lossy dedupe (hash collisions drop a line); text is redrawn every frame */

static unsigned long long fnv(unsigned long long h, const void *p, int n)
{
    const unsigned char *b = (const unsigned char *)p;
    while (n-- > 0) { h ^= *b++; h *= 1099511628211ULL; }
    return h;
}
static int first_time(unsigned long long h)
{
    unsigned i = (unsigned)(h & 2047);
    if (g_seen[i] == h) return 0;
    g_seen[i] = h; return 1;
}
static void where(char *buf, int n, void *addr)
{
    HMODULE m = NULL; char name[MAX_PATH];
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)addr, &m) && m) {
        GetModuleFileNameA(m, name, sizeof name);
        _snprintf(buf, n, "%s+0x%lx", strrchr(name, 92) ? strrchr(name, 92) + 1 : name, (unsigned long)((BYTE *)addr - (BYTE *)m));
    } else _snprintf(buf, n, "%p", addr);
    buf[n - 1] = 0;
}

/* ------------------------------------------------------------ Thai layout */

/* Plan A PoC. The engine draws text one character (or 2-char piece) per DrawTextW call at a fixed 24 px CJK step, with
   a GB2312 font. When a piece contains Thai (U+0E01..0E5B, produced by the channel above) we draw it ourselves with a
   Thai-capable font and keep our own pen per text row: spacing glyphs advance by their real width; a combining mark is
   never drawn alone (a lone mark crashed the game in PoC run 2, likely a dotted-circle glyph from shaping) -- instead the
   whole cluster (base + marks so far) is redrawn at the base position, so the font itself stacks the marks.
   Rows without Thai are passed through at the engine's own coordinates, so Chinese rendering is unchanged.
   ponytail: the base glyph is drawn twice when marks follow (slightly darker edges); fix = defer base drawing to end of frame.
   Calibration knobs (ini): thai_face, thai_scale_pct (Thai fonts look small at the same cell height), thai_dy (baseline shift). */
static int  g_thai_layout = 1;
static char g_thai_face[64] = "Tahoma";
static int  g_thai_scale = 130;          /* % of the engine font height */
static int  g_thai_dy = 999;             /* px; 999 = auto, -(thai_h - h)/2 */
static int  g_engine_glyphs = 1;         /* 1 = draw Thai with the engine's own font (crash-free in PoC v4); 0 = own font, auto-falls back on exception */
static int  g_thai_charset = 1;          /* DEFAULT_CHARSET: THAI_CHARSET (222) crashed d3dx9_25 on combining marks in PoC v3 */
static PFN_CreateFontA g_real_create;
typedef HRESULT (WINAPI *PFN_GetDevice)(void *, void **);
typedef HRESULT (WINAPI *PFN_Void)(void *);
typedef ULONG   (WINAPI *PFN_Release)(void *);
typedef HRESULT (WINAPI *PFN_GetTM)(void *, TEXTMETRICA *);
static struct { void *eng, *thai; LONG dy, th, adiff; } g_tf[16];   /* adiff = Thai ascent - engine ascent (baseline match) */
static LONG g_tw[16][0x60];              /* advance cache U+0E00..0E5F per Thai font, -1 = unknown */
static struct { void *font; LONG y, last_x, our_x, adv, base_x, ty, h; WCHAR cl[8]; int cln, used, pend, fi, kst, kval; LONG kx, ky; void *self, *spr; DWORD col; } g_ln[32];
static int g_ln_next, g_tw_init;

static int is_thai(WCHAR c)  { return c >= 0x0E01 && c <= 0x0E5B; }
static int is_mark(WCHAR c)  { return c == 0x0E31 || (c >= 0x0E34 && c <= 0x0E3A) || (c >= 0x0E47 && c <= 0x0E4E); }
static INT thai_draw(void *f, void *spr, const WCHAR *c, int n, RECT *rc, DWORD fmt, DWORD col)
{
    return ((PFN_DrawTextW)(*(void ***)f)[15])(f, spr, c, n, rc, fmt, col);
}
static int thai_font(void *eng)          /* index into g_tf or -1 */
{
    int i, fr = -1, th; void *dev = NULL, *f = NULL; HRESULT hr; FDESC d;
    for (i = 0; i < 16; i++) {
        if (g_tf[i].eng == eng) return g_tf[i].thai ? i : -1;
        if (!g_tf[i].eng && fr < 0) fr = i;
    }
    if (fr < 0 || !g_real_create || !g_vt_orig) return -1;
    memset(&d, 0, sizeof d);
    if (FAILED(((PFN_GetDescA)g_vt_orig[4])(eng, &d)) || FAILED(((PFN_GetDevice)g_vt_orig[3])(eng, &dev)) || !dev) return -1;
    th = d.H * g_thai_scale / 100;           /* empty thai_face = a larger copy of the engine's own face + charset (Q12) */
    hr = g_real_create(dev, th, 0, d.Wt ? d.Wt : FW_NORMAL, 1, FALSE, g_thai_face[0] ? (DWORD)g_thai_charset : d.Cs, OUT_DEFAULT_PRECIS, d.Q,
                       DEFAULT_PITCH | FF_DONTCARE, g_thai_face[0] ? g_thai_face : d.Face, &f);
    ((PFN_Release)(*(void ***)dev)[2])(dev);
    g_tf[fr].eng = eng; g_tf[fr].thai = SUCCEEDED(hr) ? f : NULL;
    g_tf[fr].th = th; g_tf[fr].adiff = th - d.H;
    if (f) {                                 /* ASCII is drawn with the engine font: align it on the Thai baseline */
        TEXTMETRICA te, tt;
        if (SUCCEEDED(((PFN_GetTM)g_vt_orig[6])(eng, &te)) && SUCCEEDED(((PFN_GetTM)(*(void ***)f)[6])(f, &tt))) g_tf[fr].adiff = tt.tmAscent - te.tmAscent;
    }
    g_tf[fr].dy = (g_thai_dy == 999) ? -(th - d.H) / 2 : g_thai_dy;
    if (!g_tw_init) { memset(g_tw, 0xff, sizeof g_tw); g_tw_init = 1; }
    memset(g_tw[fr], 0xff, sizeof g_tw[fr]);
    hooklog("thai font: h=%d (engine %d) dy=%ld ascii_dy=%ld charset=%d face=\"%s\" hr=0x%08lx (engine font %p, face \"%s\")",
            th, d.H, g_tf[fr].dy, g_tf[fr].adiff, g_thai_face[0] ? g_thai_charset : d.Cs, g_thai_face[0] ? g_thai_face : d.Face, (unsigned long)hr, eng, d.Face);
    return g_tf[fr].thai ? fr : -1;
}
static INT draw_t(int fi, void *self, void *spr, const WCHAR *c, int n, RECT *rc, DWORD fmt, DWORD col)
{   /* the engine font goes through g_real_draww directly: its vtable is our wrapped copy */
    return g_engine_glyphs ? g_real_draww(self, spr, c, n, rc, fmt, col) : thai_draw(g_tf[fi].thai, spr, c, n, rc, fmt, col);
}
static LONG thai_width(int fi, void *self, WCHAR c)  /* spacing characters only -- never called for a combining mark */
{
    RECT rc = {0, 0, 0, 0}; LONG *w = &g_tw[fi][c - 0x0E00];
    if (*w < 0) { draw_t(fi, self, NULL, &c, 1, &rc, DT_CALCRECT | DT_NOCLIP, 0); *w = rc.right - rc.left; }
    return *w;
}
static int row_for(void *font, LONG y)
{
    int i;
    for (i = 0; i < 32; i++) if (g_ln[i].used && g_ln[i].font == font && g_ln[i].y == y) return i;
    i = g_ln_next; g_ln_next = (g_ln_next + 1) & 31;
    memset(&g_ln[i], 0, sizeof g_ln[i]);
    g_ln[i].used = 1; g_ln[i].font = font; g_ln[i].y = y; g_ln[i].last_x = 0x7fffffff;
    return i;
}
static void tlog(WCHAR c, LONG x, LONG y, LONG w, int cln)
{
    unsigned long long h = 1469598103934665603ULL;
    if (!g_log_draw || g_lines >= g_max_lines) return;
    h = fnv(fnv(fnv(h, &c, sizeof c), &x, sizeof x), &y, sizeof y);
    if (first_time(h)) hooklog("    thai U+%04X at (%ld,%ld) w=%ld cluster=%d", (unsigned)c, x, y, w, cln);
}
/* A cluster (base + following marks / SARA AM) is drawn ONCE, when the next spacing character arrives on that row, or at the start
   of the row's next pass (the engine redraws every frame, so the last cluster of a frame is drawn one frame late -- invisible).
   This removes the double-drawn base of v3/v4 (darker glyphs on lines with many marks). */
static void flush(int k)
{
    RECT rc; LONG h = g_ln[k].h;
    if (!g_ln[k].pend) return;
    g_ln[k].pend = 0;
    SetRect(&rc, g_ln[k].base_x, g_ln[k].ty, g_ln[k].base_x + 3 * h, g_ln[k].ty + 2 * h);
    draw_t(g_ln[k].fi, g_ln[k].self, g_ln[k].spr, g_ln[k].cl, g_ln[k].cln, &rc, DT_NOCLIP, g_ln[k].col);
    tlog(g_ln[k].cl[0], g_ln[k].base_x, g_ln[k].ty, 0, g_ln[k].cln);
}
static LONG thai_piece(int k, int fi, void *self, void *spr, LPCWSTR s, int n, LPRECT r, DWORD fmt, DWORD col, LONG pen)
{
    int i; RECT rc; LONG h = r->bottom - r->top, ty = r->top + (g_engine_glyphs ? 0 : g_tf[fi].dy);
    for (i = 0; i < n; i++) {
        WCHAR c = s[i];
        if (is_thai(c) && (is_mark(c) || c == 0x0E33)) {     /* joins the pending cluster; SARA AM also has a spacing part */
            if (!g_ln[k].pend || g_ln[k].cln >= 7) { tlog(c, pen, r->top, -1, 0); continue; }   /* orphan: skip, never draw alone */
            g_ln[k].cl[g_ln[k].cln++] = c;
            if (c == 0x0E33) {
                RECT m = {0, 0, 0, 0};
                draw_t(fi, self, NULL, g_ln[k].cl, g_ln[k].cln, &m, DT_CALCRECT | DT_NOCLIP, 0);
                pen = g_ln[k].base_x + (m.right - m.left);
            }
        } else if (is_thai(c)) {
            flush(k);
            g_ln[k].pend = 1; g_ln[k].cl[0] = c; g_ln[k].cln = 1; g_ln[k].base_x = pen;
            g_ln[k].fi = fi; g_ln[k].self = self; g_ln[k].spr = spr; g_ln[k].col = col; g_ln[k].ty = ty; g_ln[k].h = h;
            pen += thai_width(fi, self, c);
        } else {                                             /* ASCII / CJK inside a Thai piece: engine font, measured */
            RECT m = {0, 0, 0, 0};
            flush(k);
            g_real_draww(self, NULL, &c, 1, &m, DT_CALCRECT, col);
            SetRect(&rc, pen, r->top, pen + 2 * h, r->bottom);
            g_real_draww(self, spr, &c, 1, &rc, fmt, col);
            pen += m.right - m.left;
        }
    }
    return pen;
}

/* ---------------------------------------------------- key expansion (no byte budget) */

/* A translated string slot holds only a 6-byte KEY: U+E000 marker + two base-128 digits U+E100.. (Thai channel v3, see
   tools/build_keys.py). When a row shows a complete key, the full Thai text from FS3_TH_text.txt is laid out once (wrapped at
   U+200B / space opportunities to wrap_width px, '*' forces a break, line pitch = line_pitch_pct of the font height), cached,
   and drawn every frame with the engine font as clusters. The engine itself only ever draws the 3 key characters, so the
   string's original byte length no longer limits the translation.
   ponytail: typewriter reveal is lost for expanded lines (whole text appears at once); emulate later if wanted. */
#define TXT_FILE "FS3_TH_text.txt"
#define MAXID    16384
#define MAXCL    320
static WCHAR *g_txt[MAXID];
static int g_wrap_w = 504;               /* px: 21 CJK cells, the widest line the original authors used */
static int g_pitch_pct = 108;            /* 26 px pitch for the 24 px dialogue font (measured, text-pipeline.md) */
static struct lay { int id, fi, wrap; void *font; LONG h, wend; int n; struct { short x, y, st, len; } c[MAXCL]; } g_lay[64];   /* menus show dozens of labels: 8 entries re-laid them out every frame */
static int g_lay_next, g_keys_off, g_box_lines, g_quiet;   /* box_lines: overflow check limit (0 = no check) */

static void load_text(void)
{
    char path[MAX_PATH]; FILE *f; long sz; char *buf, *p, *e; int count = 0;
    _snprintf(path, sizeof path, "%s%s", g_dir, TXT_FILE); path[sizeof path - 1] = 0;
    f = fopen(path, "rb");
    if (!f) { hooklog("no %s -- key expansion disabled", TXT_FILE); return; }
    fseek(f, 0, SEEK_END); sz = ftell(f); fseek(f, 0, SEEK_SET);
    buf = (char *)malloc(sz + 1);
    if (!buf) { fclose(f); return; }
    sz = (long)fread(buf, 1, sz, f); buf[sz] = 0; fclose(f);
    p = buf;
    if (sz >= 3 && (unsigned char)p[0] == 0xEF && (unsigned char)p[1] == 0xBB && (unsigned char)p[2] == 0xBF) p += 3;
    while (*p) {
        char *tab; int id, n;
        e = p; while (*e && *e != 10) e++;
        if (e > p && e[-1] == 13) e[-1] = 0;
        if (*e) *e++ = 0;
        tab = strchr(p, 9);
        if (p[0] != '#' && tab) {
            id = atoi(p); tab++;
            n = MultiByteToWideChar(CP_UTF8, 0, tab, -1, NULL, 0);
            if (id > 0 && id < MAXID && n > 0 && (g_txt[id] = (WCHAR *)malloc(n * sizeof(WCHAR))) != NULL) {
                MultiByteToWideChar(CP_UTF8, 0, tab, -1, g_txt[id], n); count++;
            }
        }
        p = e;
    }
    free(buf);
    hooklog("key expansion: %d texts loaded from %s", count, TXT_FILE);
}
static int key_fi(void *self) { return g_engine_glyphs ? -1 : thai_font(self); }      /* -1 = engine font */
static INT kdraw(int fi, void *self, void *spr, const WCHAR *s, int n, RECT *rc, DWORD fmt, DWORD col)
{
    return fi < 0 ? g_real_draww(self, spr, s, n, rc, fmt, col) : thai_draw(g_tf[fi].thai, spr, s, n, rc, fmt, col);
}
static LONG measure(int fi, void *self, const WCHAR *s, int n)
{
    RECT rc = {0, 0, 0, 0};
    kdraw(fi, self, NULL, s, n, &rc, DT_CALCRECT | DT_NOCLIP, 0);
    return rc.right - rc.left;
}
static LONG space_width(int fi, void *self, LONG h)   /* CALCRECT drops a lone space (keys_shot1: words ran together) -> measure 'x x' - 'xx' */
{
    static const WCHAR xsx[] = {120, 32, 120, 0}, xx[] = {120, 120, 0};
    LONG w = measure(fi, self, xsx, 3) - measure(fi, self, xx, 2);
    return w > 0 ? w : h / 4;
}
/* Per-panel wrap widths: the engine wraps non-dialogue text itself (item help: 14 cells per draw call), so a key only knows where
   it is drawn. wrap_rules = "h@x=px,..." (font height @ key x +-4, x 0 = any x, ">x" = x or further right; centred labels
   move with the name); "/e" after px = draw at the engine's own size there (narrow panels). First match wins, else
   wrap_width. ":y" after x also requires the key's y (+-2): panels sharing an x (tabs above a list). Every new (key, height,
   x) is logged as "key N at h= x= y=" so rules can be read off the log. */
static struct { int h, x, y, w, ge, eng; } g_wr[32];
static int g_nwr;
static void load_wrap_rules(const char *v)
{
    while (*v && g_nwr < 32) {
        int h, x, y = 0, w, used = 0, ge = 0;
        while (*v == ' ') v++;
        if (sscanf(v, "%d@%n", &h, &used) == 1 && used) {
            v += used; if (*v == '>') { ge = 1; v++; }
            if (sscanf(v, "%d%n", &x, &used) == 1) {
                v += used;
                if (*v == ':' && sscanf(v + 1, "%d%n", &y, &used) == 1) v += 1 + used;
                if (*v == '=' && sscanf(v + 1, "%d%n", &w, &used) == 1) {
                    v += 1 + used; g_wr[g_nwr].h = h; g_wr[g_nwr].x = x; g_wr[g_nwr].y = y; g_wr[g_nwr].w = w; g_wr[g_nwr].ge = ge;
                    g_wr[g_nwr].eng = (v[0] == '/' && (v[1] == 'e' || v[1] == 'E')); g_nwr++;
                }
            }
        }
        while (*v && *v != ',') v++;
        if (*v == ',') v++;
    }
}
static int rule_for(LONG h, LONG x, LONG y)  /* index into g_wr or -1 */
{
    int i;
    for (i = 0; i < g_nwr; i++)
        if (g_wr[i].h == h && (g_wr[i].x == 0 || (g_wr[i].ge ? x >= g_wr[i].x : (x >= g_wr[i].x - 4 && x <= g_wr[i].x + 4)))
            && (g_wr[i].y == 0 || (y >= g_wr[i].y - 2 && y <= g_wr[i].y + 2))) return i;
    return -1;
}
static struct lay *layout_text(int fi, void *self, int id, LONG h, int wrap)
{
    struct lay *L; const WCHAR *t = g_txt[id]; int i, j, len, n = 0, line = 0, ls = 0, lb = -1, k; LONG x = 0, w;
    for (i = 0; i < 64; i++) if (g_lay[i].id == id && g_lay[i].fi == fi && g_lay[i].wrap == wrap && g_lay[i].font == self && g_lay[i].h == h) return &g_lay[i];
    L = &g_lay[g_lay_next]; g_lay_next = (g_lay_next + 1) & 63;
    L->id = id; L->fi = fi; L->wrap = wrap; L->font = self; L->h = h; L->n = 0;
    len = (int)wcslen(t);
    for (i = 0; i < len && n < MAXCL; i = j) {
        WCHAR c = t[i]; j = i + 1;
        if (c == 42) { line++; x = 0; ls = n; lb = -1; continue; }              /* '*' forced break */
        if (c == 0x200B) { lb = n; continue; }                                  /* allowed break before the next cluster */
        if (is_thai(c) && (is_mark(c) || c == 0x0E33)) continue;               /* orphan mark: never draw alone */
        if (is_thai(c)) while (j < len && is_thai(t[j]) && (is_mark(t[j]) || t[j] == 0x0E33)) j++;
        w = (c == 32) ? space_width(fi, self, h) : measure(c < 0x80 ? -1 : fi, self, &t[i], j - i);   /* ASCII: engine size (Kaiti Latin is huge when scaled) */
        if (x + w > wrap && n > ls) {
            if (lb > ls && lb <= n) {                                          /* move the clusters after the last break down */
                LONG shift = (lb < n) ? L->c[lb].x : x;
                for (k = lb; k < n; k++) { L->c[k].x = (short)(L->c[k].x - shift); L->c[k].y = (short)(line + 1); }
                x -= shift; ls = lb;
            } else { x = 0; ls = n; }                                          /* no opportunity: hard break here */
            line++; lb = -1;
        }
        L->c[n].x = (short)x; L->c[n].y = (short)line; L->c[n].st = (short)i; L->c[n].len = (short)(j - i); n++;
        x += w;
        if (c == 32) lb = n;                                                    /* break allowed after a space */
    }
    L->n = n; L->wend = x;
    if (!g_quiet && first_time(fnv(fnv(fnv(11ULL, &id, sizeof id), &wrap, sizeof wrap), &h, sizeof h))) hooklog("key %d: %d clusters on %d line(s), wrap %d px, space %ld px, font %s", id, n, line + 1, wrap, space_width(fi, self, h), fi < 0 ? "engine" : "thai");
    return L;
}
static LONG expand_draw(void *self, void *spr, DWORD col, LONG x0, LONG y0, LONG h, int id)   /* -> x after the text's last line */
{
    int ri = rule_for(h, x0, y0), wrap = ri < 0 ? g_wrap_w : g_wr[ri].w, fi = (ri >= 0 && g_wr[ri].eng) ? -1 : key_fi(self);
    struct lay *L; RECT rc; int k; LONG th = fi < 0 ? h : g_tf[fi].th, dy = fi < 0 ? 0 : g_tf[fi].dy, pitch = th * g_pitch_pct / 100;
    if (id <= 0 || id >= MAXID || !g_txt[id]) {
        unsigned long long hh = fnv(1469598103934665603ULL, &id, sizeof id);
        if (first_time(hh)) hooklog("key %d: no text in %s", id, TXT_FILE);
        return x0;
    }
    if (g_box_lines > 0) {                   /* once, with the real font: list every text that needs more lines than the box has */
        int i, k2, over = 0, lines; struct lay *C;
        g_quiet = 1;
        for (i = 1; i < MAXID; i++) if (g_txt[i]) {
            C = layout_text(fi, self, i, h, g_wrap_w);
            for (lines = 0, k2 = 0; k2 < C->n; k2++) if (C->c[k2].y + 1 > lines) lines = C->c[k2].y + 1;
            if (lines > g_box_lines) { hooklog("overflow: key %d needs %d lines (box_lines %d)", i, lines, g_box_lines); over++; }
        }
        g_quiet = 0; hooklog("overflow check: %d text(s) longer than %d lines (wrap %d px, font %s)", over, g_box_lines, g_wrap_w, fi < 0 ? "engine" : "thai");
        g_box_lines = 0; memset(g_lay, 0, sizeof g_lay);
    }
    {
        unsigned long long hh = fnv(fnv(fnv(7ULL, &id, sizeof id), &h, sizeof h), &x0, sizeof x0);
        if (first_time(hh)) hooklog("key %d at h=%ld x=%ld y=%ld wrap=%d%s", id, h, x0, y0, wrap, fi < 0 ? " engine-size" : "");
    }
    L = layout_text(fi, self, id, h, wrap); y0 += dy;
    for (k = 0; k < L->n; k++) {
        SetRect(&rc, x0 + L->c[k].x, y0 + L->c[k].y * pitch, x0 + L->c[k].x + 3 * th, y0 + L->c[k].y * pitch + 2 * th);
        if (fi >= 0 && g_txt[id][L->c[k].st] < 0x80) OffsetRect(&rc, 0, g_tf[fi].adiff);
        kdraw(g_txt[id][L->c[k].st] < 0x80 ? -1 : fi, self, spr, &g_txt[id][L->c[k].st], L->c[k].len, &rc, DT_NOCLIP, col);
    }
    return x0 + L->wend;
}
/* ---------------------------------------------- drawn-text replacement (strings hardcoded in FS3.exe) */

/* FS3.exe is never modified, so its own Chinese strings are replaced where they are drawn: FS3_TH_exe.txt holds
   "<pattern as drawn><TAB><thai>" (generated by tools/build_keys.py). %s / %d in the pattern match the values the game
   inserted; they are put into the Thai template in the same order. The result gets a dynamic text id (DYN0..MAXID-1)
   and is drawn like an expanded key. Only whole-line DrawTextW calls can match (cell-by-cell text never does). */
#define EXE_FILE "FS3_TH_exe.txt"
#define DYN0     16256
#define NREP     256
static WCHAR *g_rp[NREP], *g_rt[NREP];
static int g_nrep, g_dynn;
static unsigned long long g_mh[512]; static short g_mid[512];   /* match cache: string hash -> id (0 = no match) */

static WCHAR *utf8w(const char *a)
{
    int n = MultiByteToWideChar(CP_UTF8, 0, a, -1, NULL, 0); WCHAR *w = n > 0 ? (WCHAR *)malloc(n * sizeof(WCHAR)) : NULL;
    if (w) MultiByteToWideChar(CP_UTF8, 0, a, -1, w, n);
    return w;
}
static void load_exe_text(void)
{
    char path[MAX_PATH], line[2048]; FILE *f;
    _snprintf(path, sizeof path, "%s%s", g_dir, EXE_FILE); path[sizeof path - 1] = 0;
    if (!(f = fopen(path, "rb"))) return;
    while (g_nrep < NREP && fgets(line, sizeof line, f)) {
        char *tab = strchr(line, 9), *e = line + strlen(line);
        while (e > line && (e[-1] == 10 || e[-1] == 13)) *--e = 0;
        if (line[0] == '#' || !tab) continue;
        *tab = 0; g_rp[g_nrep] = utf8w(line); g_rt[g_nrep] = utf8w(tab + 1);
        if (g_rp[g_nrep] && g_rt[g_nrep]) g_nrep++;
    }
    fclose(f);
    hooklog("drawn-text replacement: %d patterns loaded from %s", g_nrep, EXE_FILE);
}
static int spec_len(const WCHAR *p)          /* p at '%': length of the printf spec incl. its letter */
{
    int k = 1;
    while (p[k] && !((p[k] >= 'a' && p[k] <= 'z') || (p[k] >= 'A' && p[k] <= 'Z'))) k++;
    return p[k] ? k + 1 : k;
}
static int pmatch(const WCHAR *p, const WCHAR *s, const WCHAR **cs, int *cl, int nc)   /* -> number of captures or -1 */
{
    while (*p) {
        if (p[0] == '%' && p[1] == '%') { if (*s != '%') return -1; p += 2; s++; continue; }
        if (*p == '%') {
            int L = spec_len(p), k, r; WCHAR t = p[L - 1];
            if (nc >= 8) return -1;
            if (t == 's') {                          /* shortest capture first */
                int rest = (int)wcslen(s);
                for (k = 0; k <= rest; k++) { cs[nc] = s; cl[nc] = k; if ((r = pmatch(p + L, s + k, cs, cl, nc + 1)) >= 0) return r; }
                return -1;
            } else {                                 /* number: optional padding / sign, then digits */
                const WCHAR *q = s, *d;
                while (*q == ' ' || *q == '0') { if (*q == '0' && !(q[1] >= '0' && q[1] <= '9')) break; q++; }
                if (*q == '-' || *q == '+') q++;
                d = q; while (*q >= '0' && *q <= '9') q++;
                if (q == d) return -1;
                cs[nc] = s; cl[nc] = (int)(q - s); nc++; s = q; p += L; continue;
            }
        }
        if (*p != *s) return -1;
        p++; s++;
    }
    return *s ? -1 : nc;
}
static int exe_match(const WCHAR *s, int n)  /* -> text id of the Thai replacement, 0 = none */
{
    WCHAR buf[512], out[1024]; const WCHAR *cs[8]; int cl[8], i, nc, ci, id;
    unsigned long long h; int slot;
    if (!g_nrep || n <= 0 || n >= 511) return 0;
    h = fnv(1469598103934665603ULL, s, n * 2) | 1; slot = (int)(h & 511);
    if (g_mh[slot] == h) return g_mid[slot];
    memcpy(buf, s, n * sizeof(WCHAR)); buf[n] = 0; id = 0;
    for (i = 0; i < g_nrep && !id; i++) {
        if ((nc = pmatch(g_rp[i], buf, cs, cl, 0)) < 0) continue;
        ci = 0;
        {   const WCHAR *t = g_rt[i]; int w = 0;
            while (*t && w < 1000) {
                if (t[0] == '%' && t[1] == '%') { out[w++] = '%'; t += 2; continue; }
                if (*t == '%') { int L = spec_len(t), k; if (ci < nc) for (k = 0; k < cl[ci] && w < 1000; k++) out[w++] = cs[ci][k]; ci++; t += L; continue; }
                out[w++] = *t++;
            }
            out[w] = 0;
        }
        for (id = DYN0; id < MAXID; id++) if (g_txt[id] && !wcscmp(g_txt[id], out)) break;
        if (id == MAXID) {                       /* new text: next ring slot, drop its old layout */
            int L;
            id = DYN0 + (g_dynn++ % (MAXID - DYN0));
            free(g_txt[id]); g_txt[id] = _wcsdup(out);
            for (L = 0; L < 64; L++) if (g_lay[L].id == id) g_lay[L].id = 0;
            hooklog("exe text %d matched pattern %d -> text %d", n, i, id);
        }
    }
    g_mh[slot] = h; g_mid[slot] = (short)id;
    return id;
}
static int is_key(WCHAR c) { return c == 0xE000 || (c >= 0xE100 && c < 0xE180) || (c > 0xE200 && c < 0xE280); }   /* E2xx = one-char SHORT key (slots < 6 B) */
/* Text after a key on the same row ("熱鍵" + "1", drawn cell by cell) would land at its engine position, under the
   longer Thai: the pen after the expansion (kend) is kept and the row's next pieces continue from there. */
static INT key_piece(int k, void *self, void *spr, LPCWSTR s, int n, LPRECT r, DWORD col)
{
    int i; LONG kend = -1, pen = r->left, h = r->bottom - r->top;   /* pen: text before a key ("9" + KEY) is drawn, the key follows it */
    g_ln[k].pend = 0;
    for (i = 0; i < n; i++) {
        WCHAR c = s[i];
        if (c > 0xE200 && c < 0xE280) { g_ln[k].kst = 0; g_ln[k].kx = pen; g_ln[k].ky = r->top; }
        else if (c == 0xE000) { g_ln[k].kst = 1; g_ln[k].kx = pen; g_ln[k].ky = r->top; }
        else if (c >= 0xE100 && c < 0xE180 && g_ln[k].kst == 1) { g_ln[k].kval = c - 0xE100; g_ln[k].kst = 2; }
        else if (c >= 0xE100 && c < 0xE180 && g_ln[k].kst == 2) {
            g_ln[k].kst = 0;
            g_ln[k].kval = g_ln[k].kval * 128 + (c - 0xE100);
        } else {                                    /* not a key char (before, between or after keys): draw it at the pen */
            if (!is_key(c) && g_ln[k].kst != 1 && g_ln[k].kst != 2) { RECT m = {0, 0, 0, 0}, rc;
                g_real_draww(self, NULL, &c, 1, &m, DT_CALCRECT, col);
                SetRect(&rc, pen, r->top, pen + 2 * h, r->bottom); g_real_draww(self, spr, &c, 1, &rc, DT_NOCLIP, col);
                pen += m.right - m.left; if (kend >= 0) kend = pen; }
            continue;
        }
        if (g_ln[k].kst == 0) {
            int id = (c > 0xE200 && c < 0xE280) ? c - 0xE200 : g_ln[k].kval;
            __try { pen = kend = expand_draw(self, spr, col, g_ln[k].kx, g_ln[k].ky, h, id); }
            __except (EXCEPTION_EXECUTE_HANDLER) {
                if (!g_engine_glyphs) {          /* larger Thai font failed: fall back to the engine font, keep expanding */
                    hooklog("!!! exception 0x%08lx in key expansion with the Thai font -- switching to the engine font", (unsigned long)GetExceptionCode());
                    g_engine_glyphs = 1;
                } else {
                    hooklog("!!! exception 0x%08lx in key expansion -- disabled", (unsigned long)GetExceptionCode());
                    g_keys_off = 1;
                }
            }
        }
    }
    g_ln[k].last_x = r->left; g_ln[k].our_x = r->left; g_ln[k].adv = -1;
    if (kend >= 0) { g_ln[k].our_x = kend; g_ln[k].adv = 0; g_ln[k].kst = 3; }   /* next adjacent piece of this row: right after the Thai text */
    return h;
}

static INT layout_draw(void *self, void *spr, LPCWSTR s, INT cnt, LPRECT r, DWORD fmt, DWORD col)
{
    int n, i, fi, thai = 0, k; LONG x, pen; RECT rc;
    if (!r || !s || (fmt & DT_CALCRECT)) return g_real_draww(self, spr, s, cnt, r, fmt, col);
    n = (cnt < 0) ? (int)wcslen(s) : cnt;
    if (g_nrep && !g_keys_off) {                         /* a string hardcoded in FS3.exe: draw its Thai replacement */
        int id = exe_match(s, n);
        if (id) {
            __try { expand_draw(self, spr, col, r->left, r->top, r->bottom - r->top, id); }
            __except (EXCEPTION_EXECUTE_HANDLER) { hooklog("!!! exception in drawn-text replacement -- disabled"); g_nrep = 0; }
            return r->bottom - r->top;
        }
    }
    for (i = 0; i < n; i++) if (is_key(s[i])) {          /* translated slot: key -> full Thai text */
        RECT rr = *r; LONG hh = r->bottom - r->top;
        k = row_for(self, r->top);
        if (r->left > g_ln[k].last_x && r->left - g_ln[k].last_x <= 2 * hh && g_ln[k].our_x != g_ln[k].last_x)   /* follows shifted text */
            OffsetRect(&rr, g_ln[k].our_x + (g_ln[k].adv >= 0 ? g_ln[k].adv : r->left - g_ln[k].last_x) - r->left, 0);
        if (g_keys_off) return hh;
        key_piece(k, self, spr, s, n, &rr, col);
        g_ln[k].last_x = r->left;                        /* gaps are measured in engine coordinates */
        return hh;
    }
    for (i = 0; i < n; i++) if (is_thai(s[i])) thai = 1;
    k = row_for(self, r->top);
    if (r->left > g_ln[k].last_x && g_ln[k].kst == 3 && r->left - g_ln[k].last_x > 2 * (r->bottom - r->top)) x = r->left;   /* separate column after a key (stat value) */
    else if (r->left > g_ln[k].last_x) x = g_ln[k].our_x + (g_ln[k].adv >= 0 ? g_ln[k].adv : r->left - g_ln[k].last_x);
    else { __try { flush(k); } __except (EXCEPTION_EXECUTE_HANDLER) { g_ln[k].pend = 0; } x = r->left; }   /* new pass */
    g_ln[k].last_x = r->left; g_ln[k].our_x = x;
    fi = thai ? thai_font(self) : -1;
    if (fi < 0 && thai && g_engine_glyphs) fi = 0;           /* engine glyphs need no Thai font object; slot 0 = width cache only */
    if (fi < 0) {                                            /* no Thai here: engine glyphs, our x */
        __try { flush(k); } __except (EXCEPTION_EXECUTE_HANDLER) { g_ln[k].pend = 0; }
        rc = *r; OffsetRect(&rc, x - r->left, 0); g_ln[k].adv = -1;
        return g_real_draww(self, spr, s, cnt, &rc, fmt, col);
    }
    __try {
        pen = thai_piece(k, fi, self, spr, s, n, r, fmt, col, x);
    } __except (EXCEPTION_EXECUTE_HANDLER) {                 /* never take the game down */
        g_ln[k].pend = 0;
        if (!g_engine_glyphs) {                              /* first failure: the engine font is known to cope with marks */
            hooklog("!!! exception 0x%08lx while drawing Thai U+%04X with \"%s\" -- switching to the engine font",
                    (unsigned long)GetExceptionCode(), (unsigned)s[0], g_thai_face);
            g_engine_glyphs = 1; memset(g_tw, 0xff, sizeof g_tw);
        } else {
            hooklog("!!! exception 0x%08lx while drawing Thai U+%04X with the engine font -- thai_layout disabled",
                    (unsigned long)GetExceptionCode(), (unsigned)s[0]);
            g_thai_layout = 0;
        }
        pen = x + (r->right - r->left) / 2;
    }
    g_ln[k].adv = pen - x;
    return r->bottom - r->top;
}
/* keep our Thai fonts in step with the engine's: device loss/reset and final release */
static void for_thai(void *eng, int slot)
{
    int i;
    for (i = 0; i < 16; i++) if (g_tf[i].eng == eng && g_tf[i].thai) ((PFN_Void)(*(void ***)g_tf[i].thai)[slot])(g_tf[i].thai);
}
static HRESULT WINAPI my_OnLost(void *self)  { HRESULT hr = ((PFN_Void)g_vt_orig[16])(self); for_thai(self, 16); return hr; }
static HRESULT WINAPI my_OnReset(void *self) { HRESULT hr = ((PFN_Void)g_vt_orig[17])(self); for_thai(self, 17); return hr; }
static ULONG WINAPI my_Release(void *self)
{
    ULONG rc = ((PFN_Release)g_vt_orig[2])(self); int i;
    if (rc == 0) {
        for (i = 0; i < 16; i++) if (g_tf[i].eng == self) {
            if (g_tf[i].thai) ((PFN_Release)(*(void ***)g_tf[i].thai)[2])(g_tf[i].thai);
            g_tf[i].eng = g_tf[i].thai = NULL;
        }
        for (i = 0; i < 32; i++) if (g_ln[i].font == self) g_ln[i].used = 0;
    }
    return rc;
}

static INT WINAPI my_DrawTextA(void *self, void *spr, LPCSTR s, INT cnt, LPRECT r, DWORD fmt, DWORD col)
{
    RECT in = {0, 0, 0, 0}; INT ret; int n = 0;
    if (r) in = *r;
    ret = g_real_drawa(self, spr, s, cnt, r, fmt, col);
    if (g_log_draw && s && g_lines < g_max_lines) {
        unsigned long long h = 1469598103934665603ULL; char w[160];
        n = (cnt < 0) ? (int)strlen(s) : cnt;
        h = fnv(fnv(fnv(h, s, n), &in, sizeof in), &fmt, sizeof fmt);
        if (first_time(h)) {
            where(w, sizeof w, _ReturnAddress());
            hooklog("DrawTextA ret=%d cnt=%d fmt=0x%lx col=%08lx rect_in=(%ld,%ld,%ld,%ld) rect_out=(%ld,%ld,%ld,%ld) caller=%s sprite=%d",
                    ret, cnt, (unsigned long)fmt, (unsigned long)col, in.left, in.top, in.right, in.bottom,
                    r ? r->left : 0, r ? r->top : 0, r ? r->right : 0, r ? r->bottom : 0, w, spr != NULL);
            log_bytes("bytes", (const unsigned char *)s, n);
        }
    }
    return ret;
}
static INT WINAPI my_DrawTextW(void *self, void *spr, LPCWSTR s, INT cnt, LPRECT r, DWORD fmt, DWORD col)
{
    RECT in = {0, 0, 0, 0}; INT ret; int n = 0;
    if (r) in = *r;
    ret = g_thai_layout ? layout_draw(self, spr, s, cnt, r, fmt, col) : g_real_draww(self, spr, s, cnt, r, fmt, col);
    if (g_log_draw && s && g_lines < g_max_lines) {
        unsigned long long h = 1469598103934665603ULL; char w[160];
        n = (cnt < 0) ? (int)wcslen(s) : cnt;
        h = fnv(fnv(fnv(h, s, n * 2), &in, sizeof in), &fmt, sizeof fmt);
        if (first_time(h)) {
            where(w, sizeof w, _ReturnAddress());
            hooklog("DrawTextW ret=%d cnt=%d fmt=0x%lx col=%08lx rect_in=(%ld,%ld,%ld,%ld) rect_out=(%ld,%ld,%ld,%ld) caller=%s",
                    ret, cnt, (unsigned long)fmt, (unsigned long)col, in.left, in.top, in.right, in.bottom,
                    r ? r->left : 0, r ? r->top : 0, r ? r->right : 0, r ? r->bottom : 0, w);
            log_wide("wide", s, n);
        }
    }
    return ret;
}
/* returns 1 if the vtable was patched */
static int hook_font_object(void *obj, INT h, LPCSTR face)
{
    void **vt; HMODULE owner = NULL; FDESC d;
    if ((!g_log_draw && !g_thai_layout) || !obj) return 0;
    vt = *(void ***)obj;
    if (vt == g_vt_orig) { *(void ***)obj = g_vt_copy; return 1; }          /* already built a copy for this class */
    if (g_vt_orig) return 0;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)vt[14], &owner) || owner != g_orig) {
        hooklog("    draw hook: vtable[14] is not inside d3dx9_25_orig -- layout assumption wrong, not patching"); return 0; }
    memset(&d, 0, sizeof d);
    if (FAILED(((PFN_GetDescA)vt[4])(obj, &d)) || d.H != h || (face && lstrcmpA(d.Face, face) != 0)) {
        hooklog("    draw hook: GetDescA sanity check failed (H=%d face=\"%s\") -- not patching", d.H, d.Face); return 0; }
    memcpy(g_vt_copy, vt, 18 * sizeof(void *));
    g_real_drawa = (PFN_DrawTextA)vt[14]; g_real_draww = (PFN_DrawTextW)vt[15];
    g_vt_copy[14] = (void *)my_DrawTextA; g_vt_copy[15] = (void *)my_DrawTextW;
    g_vt_copy[2] = (void *)my_Release; g_vt_copy[16] = (void *)my_OnLost; g_vt_copy[17] = (void *)my_OnReset;
    g_vt_orig = vt; *(void ***)obj = g_vt_copy;
    hooklog("    draw hook: ID3DXFont vtable verified (GetDescA echoed H=%d face=\"%s\"), DrawTextA/W wrapped", d.H, d.Face);
    return 1;
}

/* ------------------------------------------------------------- the hook */

/* Exported through the .def file, so no __declspec(dllexport) here -- naming
   it in both places makes MSVC emit LNK4197 and confuses MinGW's stdcall
   decoration. */
HRESULT WINAPI D3DXCreateFontA(void *dev, INT h, UINT w, UINT weight,
                               UINT mip, BOOL italic, DWORD charset,
                               DWORD prec, DWORD quality, DWORD pitch,
                               LPCSTR face, void **out)
{
    static PFN_CreateFontA real;
    DWORD used_charset = charset;
    LPCSTR used_face = face;
    HRESULT hr;

    if (!real) {
        /* Loaded lazily: calling LoadLibrary from DllMain runs under the
           loader lock. The .def forwarders make the loader pull the original
           in on its own anyway, so by the time we get here it is present. */
        if (!g_orig) {
            char path[MAX_PATH];
            _snprintf(path, sizeof path, "%s%s.dll", g_dir, ORIG_DLL);
            path[sizeof path - 1] = 0;
            g_orig = LoadLibraryA(path);
            if (!g_orig) g_orig = GetModuleHandleA(ORIG_DLL ".dll");
            hooklog("original dll resolved: handle=%p path=%s",
                    (void *)g_orig, path);
        }
        real = (PFN_CreateFontA)GetProcAddress(g_orig, "D3DXCreateFontA");
        g_real_create = real;
        if (!real) {
            hooklog("FATAL: original D3DXCreateFontA not found");
            return E_FAIL;
        }
    }

    hooklog("D3DXCreateFontA  height=%d width=%u weight=%u mip=%u italic=%d",
         h, w, weight, mip, italic);
    hooklog("    ORIGINAL charset=%lu  precision=%lu quality=%lu pitch=%lu face=\"%s\"",
         (unsigned long)charset, (unsigned long)prec,
         (unsigned long)quality, (unsigned long)pitch, face ? face : "(null)");

    if (g_force_charset >= 0 && (DWORD)g_force_charset != charset) {
        used_charset = (DWORD)g_force_charset;
        hooklog("    -> forcing charset %lu", (unsigned long)used_charset);
    }
    if (g_force_face[0]) {
        used_face = g_force_face;
        hooklog("    -> forcing face \"%s\"", used_face);
    }

    if (!g_hooked_textout) {
        g_hooked_textout = 1;
        install_hooks();
    }

    hr = real(dev, h, w, weight, mip, italic, used_charset, prec, quality,
              pitch, used_face, out);
    hooklog("    result=0x%08lx", (unsigned long)hr);
    if (SUCCEEDED(hr) && out && *out) hook_font_object(*out, h, used_face);
    return hr;
}

/* ------------------------------------------------------------- DllMain */

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH];
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        init_paths(inst);
        _snprintf(path, sizeof path, "%s%s", g_dir, LOG_FILE);
        path[sizeof path - 1] = 0;
        g_log = fopen(path, "w");
        load_config();
        hooklog("=== FS3 Thai hook loaded ===");
        hooklog("dir=\"%s\"  ini=\"%s\"", g_dir, g_ini);
        hooklog("force_charset=%d  force_face=\"%s\"  log_textout=%d log_mb2wc=%d max_lines=%d",
             g_force_charset, g_force_face, g_log_textout, g_log_mb2wc, g_max_lines);
        load_map();
        load_text();
        load_exe_text();
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_log) { hooklog("=== unloaded ==="); fclose(g_log); g_log = NULL; }
    }
    return TRUE;
}
