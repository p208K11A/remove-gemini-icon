@echo off
rem Remove the Gemini watermark + upscale every source video in InProgress\ -> {name}-output.mp4
rem Double-click, or: process.bat [name] [--pull] [--ai] [--sharpen 1.0] [--size 3840x2160]
python "%~dp0process.py" %*
if "%~1"=="" pause
