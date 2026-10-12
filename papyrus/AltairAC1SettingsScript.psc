Scriptname AltairAC1SettingsScript extends Quest
{Applies the Altair AC1 settings page (SKSE Menu Framework, AltairAC1Menu.dll). The page writes key=value lines to
Data/SKSE/Plugins/AltairAC1Settings.ini; this quest reads the file every second and, when it changed, sets the
globals the haystacks read, toggles the OAR animation sets (hidden abilities their conditions check), and runs the
page's buttons (each button bumps a counter in the file).}

GlobalVariable Property AltairLeapEnabled Auto
GlobalVariable Property AltairLeapGuidance Auto
GlobalVariable Property AltairLeapArmHeight Auto
GlobalVariable Property AltairLeapArmRadius Auto
GlobalVariable Property AltairLeapSafeRadius Auto
GlobalVariable Property AltairLeapReadyMessage Auto
GlobalVariable Property AltairLeapVolume Auto
GlobalVariable Property AltairDebug Auto
Spell Property AltairOffLocomotion Auto
Spell Property AltairOffParkour Auto
Spell Property AltairOffLeapDive Auto
Spell Property AltairPlaceHaystack Auto
ObjectReference Property AltairPortableHaystack Auto
ObjectReference Property AltairSolitudeHaystack Auto

String Property SettingsFile = "data/skse/plugins/AltairAC1Settings.ini" AutoReadOnly
Float Property Units = 70.0 AutoReadOnly       ; game units per metre

String lastText = ""
Bool seenFile = false
Int cmdPower = -1
Int cmdHayHere = -1
Int cmdGoto = -1

Event OnInit()
	RegisterForSingleUpdate(3.0)
EndEvent

Event OnUpdate()
	Sync()
	RegisterForSingleUpdate(1.0)
EndEvent

Function Sync()
	If !MiscUtil.FileExists(SettingsFile)
		Return
	EndIf
	String text = MiscUtil.ReadFromFile(SettingsFile)
	If text == "" || text == lastText
		Return
	EndIf
	Bool first = !seenFile
	seenFile = true
	lastText = text
	String[] lines = PapyrusUtil.StringSplit(text, "\n")
	Int i = 0
	While i < lines.Length
		String[] kv = PapyrusUtil.StringSplit(lines[i], "=")
		If kv.Length == 2
			Apply(kv[0], kv[1], first)
		EndIf
		i += 1
	EndWhile
	If AltairDebug.GetValue() > 0.0
		Debug.Notification("[debug] Altair AC1 settings applied")
	EndIf
EndFunction

Function Toggle(Spell offSpell, Bool on)
	Actor player = Game.GetPlayer()
	If on
		player.RemoveSpell(offSpell)
	ElseIf !player.HasSpell(offSpell)
		player.AddSpell(offSpell, false)
	EndIf
EndFunction

; buttons: counters in the file; the first read after loading only records them, so old presses never replay
Bool Function Pressed(Int value, Int last, Bool first)
	Return !first && last >= 0 && value != last
EndFunction

Function Apply(String name, String value, Bool first)
	Float v = value as Float
	If name == "leap_enabled"
		AltairLeapEnabled.SetValue(v)
	ElseIf name == "leap_guidance"
		AltairLeapGuidance.SetValue(v)
	ElseIf name == "leap_arm_height"
		AltairLeapArmHeight.SetValue(v * Units)
	ElseIf name == "leap_arm_radius"
		AltairLeapArmRadius.SetValue(v * Units)
	ElseIf name == "leap_safe_radius"
		AltairLeapSafeRadius.SetValue(v * Units)
	ElseIf name == "leap_ready_message"
		AltairLeapReadyMessage.SetValue(v)
	ElseIf name == "leap_volume"
		AltairLeapVolume.SetValue(v)
	ElseIf name == "debug"
		AltairDebug.SetValue(v)
	ElseIf name == "anim_locomotion"
		Toggle(AltairOffLocomotion, v > 0.0)
	ElseIf name == "anim_parkour"
		Toggle(AltairOffParkour, v > 0.0)
	ElseIf name == "anim_leap_dive"
		Toggle(AltairOffLeapDive, v > 0.0)
	ElseIf name == "cmd_power"
		If Pressed(v as Int, cmdPower, first)
			Game.GetPlayer().AddSpell(AltairPlaceHaystack)
		EndIf
		cmdPower = v as Int
	ElseIf name == "cmd_hay_here"
		If Pressed(v as Int, cmdHayHere, first)
			PlaceHaystackHere()
		EndIf
		cmdHayHere = v as Int
	ElseIf name == "cmd_goto_solitude"
		If Pressed(v as Int, cmdGoto, first)
			Game.GetPlayer().MoveTo(AltairSolitudeHaystack, 0.0, 0.0, 200.0)
		EndIf
		cmdGoto = v as Int
	EndIf
EndFunction

Function PlaceHaystackHere()
	Actor player = Game.GetPlayer()
	Float a = player.GetAngleZ()
	AltairPortableHaystack.Disable()
	AltairPortableHaystack.MoveTo(player, 260.0 * Math.Sin(a), 260.0 * Math.Cos(a), 0.0)
	AltairPortableHaystack.SetAngle(0.0, 0.0, a)
	AltairPortableHaystack.Enable()
	(AltairPortableHaystack as AltairHaystackScript).StartWatching()
EndFunction
