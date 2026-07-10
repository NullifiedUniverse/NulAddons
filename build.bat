@echo off
REM Null's Addons - one-command mod build (Windows).
REM Usage:  build.bat [all|fabric|forge]
REM
REM No Gradle install needed (each mod ships a wrapper). You DO need a JDK:
REM   Fabric (Minecraft 1.21) -> JDK 21     Forge (Minecraft 1.8.9) -> JDK 8
REM Finished jars land in .\dist\ - drop the right one into your 'mods' folder.

setlocal
set ROOT=%~dp0
if not exist "%ROOT%dist" mkdir "%ROOT%dist"
set TARGET=%1
if "%TARGET%"=="" set TARGET=all

if "%TARGET%"=="fabric" goto fabric
if "%TARGET%"=="forge" goto forge
if "%TARGET%"=="all" goto all
echo usage: build.bat [all^|fabric^|forge]
exit /b 1

:fabric
call :build mod-fabric "Fabric (Minecraft 1.21, needs JDK 21)"
goto done
:forge
call :build mod "Forge (Minecraft 1.8.9, needs JDK 8)"
goto done
:all
call :build mod-fabric "Fabric (Minecraft 1.21, needs JDK 21)"
call :build mod "Forge (Minecraft 1.8.9, needs JDK 8)"
goto done

:build
echo Building %~2 ...
pushd "%ROOT%%~1"
call gradlew.bat --console=plain build
popd
copy /y "%ROOT%%~1\build\libs\*.jar" "%ROOT%dist\" >nul 2>&1
echo Done %~2.
exit /b 0

:done
echo Jars are in %ROOT%dist\  - copy the one for your Minecraft version into 'mods'.
endlocal
