/* install.exe / uninstall.exe: runs python\python.exe -I install.py install|uninstall next to this exe (embedded Python, nothing to install).
   Built as install.exe; a copy named uninstall.exe selects "uninstall" by its own name. cl /O2 /MT launcher.c */
#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    char me[MAX_PATH], dir[MAX_PATH], cmd[MAX_PATH * 3]; STARTUPINFOA si = { sizeof si }; PROCESS_INFORMATION pi; DWORD code = 1;
    GetModuleFileNameA(NULL, me, MAX_PATH); strcpy(dir, me); *strrchr(dir, '\\') = 0;
    SetConsoleOutputCP(65001);
    _snprintf(cmd, sizeof cmd, "\"%s\\python\\python.exe\" -I \"%s\\install.py\" %s", dir, dir, strstr(strrchr(me, '\\'), "uninstall") ? "uninstall" : "install");
    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) { printf("Cannot start %s (error %lu)\nUnzip the whole FS3_Thai folder first.\n", cmd, GetLastError()); system("pause"); return 1; }
    WaitForSingleObject(pi.hProcess, INFINITE); GetExitCodeProcess(pi.hProcess, &code); return (int)code;
}
