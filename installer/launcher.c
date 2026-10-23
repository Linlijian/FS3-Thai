/* FS3_Thai_Setup.exe: the whole player package in one file. make_dist.py appends a zip (app.zip, mod/, python/) to this exe,
   followed by its size (u32) and the magic "FS3THPK1". On start the zip is copied to %TEMP%\FS3_Thai_<pid>, unpacked with
   Windows' own tar.exe (Windows 10 1803+) and python\python.exe -I app.zip menu|install|uninstall runs there; the folder is
   removed afterwards. Without a payload (development) it runs the package folder next to the exe, as before: install.exe /
   uninstall.exe (a copy named uninstall*.exe selects "uninstall" by its own name).
   cl /O2 /MT launcher.c shell32.lib /link /MANIFEST:EMBED /MANIFESTINPUT:launcher.manifest (asInvoker: without it Windows
   treats "install*.exe" / "*setup*.exe" as needing UAC elevation) */
#include <windows.h>
#include <shellapi.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#define MAGIC "FS3THPK1"
static int run(char *cmd, const char *dir)          /* -> exit code, -1 = could not start */
{
    STARTUPINFOA si = { sizeof si }; PROCESS_INFORMATION pi; DWORD code = 1;
    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) return -1;
    WaitForSingleObject(pi.hProcess, INFINITE); GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess); return (int)code;
}
static int unpack(const char *me, char *dir)        /* payload -> dir (created); 0 = no payload, -1 = error, 1 = ok */
{
    FILE *f = fopen(me, "rb"), *o; char tail[12], zip[MAX_PATH], cmd[MAX_PATH * 3], buf[1 << 16]; long end; unsigned long size, left; size_t got;
    if (!f) return -1;
    fseek(f, -12, SEEK_END); end = ftell(f);
    if (fread(tail, 1, 12, f) != 12 || memcmp(tail + 4, MAGIC, 8)) { fclose(f); return 0; }
    memcpy(&size, tail, 4); fseek(f, end - (long)size, SEEK_SET);
    GetTempPathA(MAX_PATH, dir); _snprintf(dir + strlen(dir), MAX_PATH - strlen(dir) - 1, "FS3_Thai_%lu", GetCurrentProcessId());
    CreateDirectoryA(dir, NULL); _snprintf(zip, sizeof zip, "%s\\payload.zip", dir);
    if (!(o = fopen(zip, "wb"))) { fclose(f); return -1; }
    for (left = size; left && (got = fread(buf, 1, left < sizeof buf ? left : sizeof buf, f)) > 0; left -= (unsigned long)got) fwrite(buf, 1, got, o);
    fclose(o); fclose(f);
    if (left) return -1;
    printf("Unpacking...\n");
    _snprintf(cmd, sizeof cmd, "tar.exe -xf \"%s\"", zip);
    if (run(cmd, dir) != 0) { printf("Cannot unpack (Windows 10 or newer is needed for tar.exe).\n"); return -1; }
    DeleteFileA(zip);
    return 1;
}
static void remove_tree(const char *dir)
{
    char from[MAX_PATH + 2] = {0}; SHFILEOPSTRUCTA op = {0};
    strncpy(from, dir, MAX_PATH);                      /* double-NUL terminated */
    op.wFunc = FO_DELETE; op.pFrom = from; op.fFlags = FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT;
    SHFileOperationA(&op);
}
int main(void) {
    char me[MAX_PATH], dir[MAX_PATH], cmd[MAX_PATH * 3]; const char *args, *mode; int code, packed;
    GetModuleFileNameA(NULL, me, MAX_PATH); strcpy(dir, me); *strrchr(dir, '\\') = 0;
    SetConsoleOutputCP(65001);
    { char *a = GetCommandLineA(); if (*a == '"') { a = strchr(a + 1, '"'); if (a) a++; } else { while (*a && *a != ' ') a++; } while (a && *a == ' ') a++; args = a ? a : ""; }
    packed = unpack(me, dir);
    if (packed < 0) { system("pause"); return 1; }
    if (!strncmp(args, "install", 7) || !strncmp(args, "uninstall", 9) || !strncmp(args, "menu", 4)) mode = "";   /* given on the command line */
    else if (strstr(strrchr(me, '\\'), "uninstall")) mode = "uninstall";
    else mode = packed ? "menu" : "install";
    _snprintf(cmd, sizeof cmd, "\"%s\\python\\python.exe\" -I \"%s\\app.zip\" %s %s", dir, dir, mode, args);
    code = run(cmd, dir);
    if (code < 0) { printf("Cannot start %s (error %lu)\nUnzip the whole FS3_Thai folder first.\n", cmd, GetLastError()); system("pause"); }
    if (packed) remove_tree(dir);
    return code;
}
