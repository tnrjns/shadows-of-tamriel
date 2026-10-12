Scriptname AltairHaystackScript extends ObjectReference
{A leap-of-faith haystack. While loaded it watches the player: standing high enough above it and close enough
sideways arms the AC1 dive (the ability switches the jump/fall/land animations through Open Animation Replacer).
Jumping while armed plays the AC1 leap sound and (guidance) carries the player toward the hay; falling into the
column above the hay switches fall damage off (SKSE game setting fJumpFallHeightMin), restored after the landing.
Distances, guidance, message and volume come from the Altair AC1 settings page (globals).}

Spell Property AltairLeapDive Auto
Spell Property AltairPlaceHaystack Auto
Sound Property AltairLeapOfFaithSound Auto
Sound Property AltairHaystackLandSound Auto
GlobalVariable Property AltairLeapEnabled Auto
GlobalVariable Property AltairLeapGuidance Auto
GlobalVariable Property AltairLeapArmHeight Auto
GlobalVariable Property AltairLeapArmRadius Auto
GlobalVariable Property AltairLeapSafeRadius Auto
GlobalVariable Property AltairLeapReadyMessage Auto
GlobalVariable Property AltairLeapVolume Auto
GlobalVariable Property AltairDebug Auto

Float Property SafeFallHeight = 100000.0 AutoReadOnly
Float Property Gravity = 686.0 AutoReadOnly          ; 9.8 m/s^2 in game units
Float Property MaxPull = 1500.0 AutoReadOnly         ; sideways correction at full guidance (21 m)

Actor player
Int stage = 0              ; 0 watching, 1 armed, 2 leaping
Bool caught = false
Float savedFall = -1.0
Float leapTime = 0.0
Bool guided = false
Float guideEnd = 0.0         ; real time the guided dive reaches the hay
Bool hitSoundPlayed = false   ; the hay sound plays at the moment of impact, not after the landing

Event OnInit()
	StartWatching()
EndEvent

Event OnCellAttach()
	StartWatching()
EndEvent

Event OnLoad()
	player = Game.GetPlayer()
	If AltairDebug.GetValue() > 0.0
		Debug.Notification("[debug] haystack script running")
	EndIf
	If AltairPlaceHaystack && !player.HasSpell(AltairPlaceHaystack)
		player.AddSpell(AltairPlaceHaystack)
	EndIf
	stage = 0
	RegisterForSingleUpdate(0.5)
EndEvent

Event OnUnload()
	UnregisterForUpdate()
	If stage == 1
		Disarm()
	EndIf
EndEvent

Function StartWatching()
	player = Game.GetPlayer()
	If stage == 1
		Disarm()
	EndIf
	stage = 0
	RegisterForSingleUpdate(0.5)
EndFunction

Function Disarm()
	UnregisterForAnimationEvent(player, "JumpUp")
	player.RemoveSpell(AltairLeapDive)
	stage = 0
EndFunction

Float Function HayTop()
	Return GetPositionZ() + GetHeight() * 0.7
EndFunction

Event OnUpdate()
	If !player
		player = Game.GetPlayer()
	EndIf
	If IsDisabled()
		Return
	EndIf
	If !Is3DLoaded()
		If player.GetWorldSpace() == GetWorldSpace()
			RegisterForSingleUpdate(3.0)      ; same worldspace: keep checking until it loads
		EndIf
		Return
	EndIf
	Float dx = player.GetPositionX() - GetPositionX()
	Float dy = player.GetPositionY() - GetPositionY()
	Float side = Math.Sqrt(dx * dx + dy * dy)
	Float height = player.GetPositionZ() - GetPositionZ()
	Bool inAir = player.GetAnimationVariableBool("bInJumpState")
	Float armHeight = AltairLeapArmHeight.GetValue()
	Float armRadius = AltairLeapArmRadius.GetValue()

	If stage == 0
		If AltairLeapEnabled.GetValue() > 0.0 && !inAir && height > armHeight && side < armRadius
			player.AddSpell(AltairLeapDive, false)
			If AltairLeapReadyMessage.GetValue() > 0.0
				Debug.Notification("Leap of Faith ready")
			EndIf
			RegisterForAnimationEvent(player, "JumpUp")
			stage = 1
			RegisterForSingleUpdate(0.2)
		ElseIf side < 4000.0
			RegisterForSingleUpdate(0.3)
		Else
			RegisterForSingleUpdate(1.5)
		EndIf
	ElseIf stage == 1
		If !inAir && (AltairLeapEnabled.GetValue() <= 0.0 || height < armHeight - 100.0 || side > armRadius + 150.0)
			Disarm()
		EndIf
		RegisterForSingleUpdate(0.2)
	ElseIf stage == 2
		If !guided && Utility.GetCurrentRealTime() - leapTime > 0.12
			guided = true
			Guide()
		EndIf
		; the instant he reaches the hay: its sound now (waiting for the landing to finish made it late)
		If caught && !hitSoundPlayed && player.GetPositionZ() - HayTop() < 60.0
			hitSoundPlayed = true
			Int hid = AltairHaystackLandSound.Play(Self)
			Sound.SetInstanceVolume(hid, AltairLeapVolume.GetValue())
		EndIf
		If side < AltairLeapSafeRadius.GetValue() && !caught
			caught = true
			savedFall = Game.GetGameSettingFloat("fJumpFallHeightMin")
			Game.SetGameSettingFloat("fJumpFallHeightMin", SafeFallHeight)
		EndIf
		Float now = Utility.GetCurrentRealTime()
		If inAir || now - leapTime < 0.4 || now < guideEnd
			RegisterForSingleUpdate(0.05)
		Else
			Landed()
		EndIf
	EndIf
EndEvent

; Carry the player toward the hay along a straight dive line, timed like a free fall from this height.
; Guidance 0 = off, 1 = straight into the centre from up to 21 m away; in between the sideways correction is limited.
Function Guide()
	Float g = AltairLeapGuidance.GetValue()
	If g <= 0.0
		Return
	EndIf
	Float px = player.GetPositionX()
	Float py = player.GetPositionY()
	Float pz = player.GetPositionZ()
	Float tz = HayTop()
	Float h = pz - tz
	If h < 150.0
		Return
	EndIf
	Float dx = GetPositionX() - px
	Float dy = GetPositionY() - py
	Float d = Math.Sqrt(dx * dx + dy * dy)
	Float pull = d
	If pull > g * MaxPull
		pull = g * MaxPull
	EndIf
	Float tx = px
	Float ty = py
	If d > 1.0
		tx = px + dx / d * pull
		ty = py + dy / d * pull
	EndIf
	Float t = Math.Sqrt(2.0 * h / Gravity)
	Float dist = Math.Sqrt(pull * pull + h * h)
	Float speed = dist / t
	If speed < 500.0
		speed = 500.0
	EndIf
	If AltairDebug.GetValue() > 0.0
		Debug.Notification("[debug] guiding " + (pull as Int) + " sideways, " + (h as Int) + " down")
	EndIf
	guideEnd = Utility.GetCurrentRealTime() + dist / speed + 0.1
	player.TranslateTo(tx, ty, tz, player.GetAngleX(), player.GetAngleY(), player.GetAngleZ(), speed, 0.0)
EndFunction

Event OnAnimationEvent(ObjectReference akSource, String asEventName)
	If stage == 1 && akSource == player && asEventName == "JumpUp"
		stage = 2
		caught = false
		guided = false
		guideEnd = 0.0
		hitSoundPlayed = false
		leapTime = Utility.GetCurrentRealTime()
		UnregisterForAnimationEvent(player, "JumpUp")
		Int id = AltairLeapOfFaithSound.Play(player)
		Sound.SetInstanceVolume(id, AltairLeapVolume.GetValue())
		RegisterForSingleUpdate(0.05)
	EndIf
EndEvent

Function Landed()
	player.StopTranslation()
	If caught
		If !hitSoundPlayed
			hitSoundPlayed = true
			Int id = AltairHaystackLandSound.Play(Self)
			Sound.SetInstanceVolume(id, AltairLeapVolume.GetValue())
		EndIf
		Utility.Wait(0.6)
		If savedFall > 0.0
			Game.SetGameSettingFloat("fJumpFallHeightMin", savedFall)
		EndIf
		caught = false
	EndIf
	Utility.Wait(1.0)                      ; let the haystack landing play
	player.RemoveSpell(AltairLeapDive)
	stage = 0
	RegisterForSingleUpdate(1.0)
EndFunction
