@echo off
REM Build the 32-bit proxy with MSVC. Run from a "x86 Native Tools Command
REM Prompt for VS" so cl.exe targets 32-bit -- the game is PE32/i386 and a
REM 64-bit DLL will simply not load.
REM
REM No /DEF here on purpose: the exports come from the linker pragmas in
REM exports_msvc.h. link.exe will not accept a forwarder that also carries an
REM explicit @ordinal, which is what produced LNK2001 on all 322 names.
setlocal
REM A failed link leaves a 0-byte d3dx9_25.dll behind. Copying that into the
REM game folder stops the game from starting at all, so clear it first.
if exist d3dx9_25.dll del /q d3dx9_25.dll
if exist d3dx9_proxy.obj del /q d3dx9_proxy.obj
cl /nologo /LD /O2 /DORIG_DLL=\"d3dx9_25_orig\" d3dx9_proxy.c ^
   /Fe:d3dx9_25.dll /link user32.lib gdi32.lib
if errorlevel 1 goto fail
for %%F in (d3dx9_25.dll) do if %%~zF EQU 0 goto empty
echo.
echo Built d3dx9_25.dll -- now check the export table:
echo     dumpbin /exports d3dx9_25.dll ^| findstr /i CreateFontA
echo D3DXCreateFontA must appear WITHOUT "(forwarded to ...)".
goto :eof
:empty
echo BUILD PRODUCED AN EMPTY DLL - do not install it
del /q d3dx9_25.dll
exit /b 1
:fail
echo BUILD FAILED
if exist d3dx9_25.dll del /q d3dx9_25.dll
exit /b 1
