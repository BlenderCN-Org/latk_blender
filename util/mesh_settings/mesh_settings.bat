@echo off

cd %~dp0
"C:\Program Files\blender\blender" %1 --background --python mesh_settings.py

@pause