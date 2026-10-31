@echo off
title Oficina de agentes - AOVE al Dia
cd /d "%~dp0.."
python pc\oficina.py
if errorlevel 1 pause
