@echo off
REM ^ Don't write everything to screen

REM - Set the working folder
cd /D "%~dp0"


REM - Set the running type from the bat file's name
set running_type=%~n0

REM - Call the runner
.\Engines\converter_run %running_type%
