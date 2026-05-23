@echo off
setlocal EnableDelayedExpansion

REM Create a mod Terminal (Windows Batch)

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

goto :main

:show_help
type "%SCRIPT_DIR%\help.txt"
goto :eof

:create_new
shift
set "mcver="
set "projName="

:parse_new_args
if "%~1"=="" goto :new_args_done
set "arg=%~1"
if /I "!arg!"=="-mcv" goto :set_mcver
if /I "!arg!"=="--mc-version" goto :set_mcver
if /I "!arg:~0,1!"=="-" (
    echo Warning: Unknown option !arg! >&2
    shift
    goto :parse_new_args
)
if "!projName!"=="" set "projName=!arg!"
shift
goto :parse_new_args

:set_mcver
shift
if "%~1"=="" (
    echo Error: !arg! requires a value. >&2
    exit /b 1
)
set "mcver=%~1"
shift
goto :parse_new_args

:new_args_done
if "!projName!"=="" (
    echo Error: Project name is required. >&2
    echo Usage: createamod new [--mc-version ^|-mcv ^<mcVersion^>] ^<projName^> >&2
    exit /b 1
)

echo Cloning fabric example mod...
if "!mcver!"=="" (
    echo Minecraft version: latest
    git clone https://github.com/FabricMC/fabric-example-mod.git "!projName!"
) else (
    echo Minecraft version: !mcver!
    git clone -b "!mcver!" https://github.com/FabricMC/fabric-example-mod.git "!projName!"
)

cd "!projName!"
echo.
echo Initializing project !projName!...

if exist gradlew.bat (
    call gradlew.bat genSources || echo Warning: genSources failed, you may need to run it manually.
) else (
    echo Warning: gradlew not found.
)

if not exist createamod mkdir createamod
if not exist createamod\blocks mkdir createamod\blocks
if not exist createamod\items mkdir createamod\items
if not exist createamod\entities mkdir createamod\entities

(
echo {
echo     "id": "modid",
echo     "name": "Example Mod",
echo     "version": "1.0.0",
echo     "description": "",
echo     "author": "",
echo     "minecraft-version": "1.20.6",
echo     "group": "com.example",
echo     "files": {
echo         "blocks": "blocks\*.createamod.json",
echo         "items": "items\*.createamod.json",
echo         "entities": "entities\*.createamod.json"
echo     }
echo }
) > createamod\config.createamod.json

echo.
echo CREATION READY!
echo Edit createamod\config.createamod.json and createamod\{blocks,items,entities}\*.createamod.json, then run "createamod update".
echo See "createamod help" for more info.
goto :eof

:update
if not exist ".\createamod\config.createamod.json" (
    echo Error: createamod\config.createamod.json not found in current directory.
    echo Make sure you are inside a createamod project directory.
    exit /b 1
)
echo Updating mod...
python "!SCRIPT_DIR!\generate.py"
goto :eof

:runClient
call :update
if errorlevel 1 exit /b 1
echo Starting Minecraft client...
call gradlew.bat runClient
goto :eof

:export_jar
shift
if not exist ".\createamod\config.createamod.json" (
    echo Error: createamod\config.createamod.json not found in current directory.
    echo Make sure you are inside a createamod project directory.
    exit /b 1
)
goto :eof

:main
if "%~1"=="" (
    echo createamod: error: No command specified.
    echo See "createamod help" for more information.
    exit /b 1
)

if /I "%~1"=="new" (
    call :create_new %*
    goto :end
)
if /I "%~1"=="help" goto :show_help
if /I "%~1"=="-h" goto :show_help
if /I "%~1"=="--help" goto :show_help
if /I "%~1"=="update" (
    call :update
    goto :end
)
if /I "%~1"=="runClient" (
    call :runClient
    goto :end
)
if /I "%~1"=="export" (
    call :export_jar %*
    goto :end
)

echo createamod: error: No such command.
echo See "createamod help" for more information.
exit /b 1

:end
endlocal
