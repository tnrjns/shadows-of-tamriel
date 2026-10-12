#!/usr/bin/env bash
# Compile the leap-of-faith scripts with the Creation Kit's Papyrus compiler into the MO2 mod.
# SKSE sources (Data/Scripts/Source) come first so Game.Get/SetGameSettingFloat resolve.
set -euo pipefail
GAME="/c/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition"
PC="$GAME/Papyrus Compiler/PapyrusCompiler.exe"
SRC="C:/Users/myste/Downloads/Altair Skyrim Native/mod/Altair AC1 Leap of Faith/Scripts/Source"
OUT="C:/Users/myste/AppData/Local/ModOrganizer/Skyrim Special Edition/mods/Altair AC1 Leap of Faith/Scripts"
VAN="C:/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition/Data/Source/Scripts"
PU="C:/Users/myste/AppData/Local/ModOrganizer/Skyrim Special Edition/mods/PapyrusUtil SE - Modders Scripting Utility Functions/Scripts/Source"
SKSE="C:/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition/Data/Scripts/Source"
[ -x "$PC" ] || { echo "Papyrus compiler not found - install/launch the Creation Kit first"; exit 1; }
[ -f "$VAN/ObjectReference.psc" ] || { echo "Vanilla script sources missing - launch the Creation Kit once and extract Scripts.zip"; exit 1; }
mkdir -p "$OUT"
for s in AltairHaystackScript AltairPlaceHaystackEffect AltairAC1SettingsScript; do
  "$PC" "$SRC/$s.psc" -f="TESV_Papyrus_Flags.flg" -i="$SKSE;$PU;$VAN;$SRC" -o="$OUT"
done
ls -la "$OUT"/*.pex
