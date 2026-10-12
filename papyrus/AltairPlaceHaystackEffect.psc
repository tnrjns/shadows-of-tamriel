Scriptname AltairPlaceHaystackEffect extends ActiveMagicEffect
{Place Haystack (lesser power): moves the portable leap-of-faith haystack onto the ground a few steps in front of
the caster. Cast it where you want to land, then climb to anything high above it and jump.}

ObjectReference Property AltairPortableHaystack Auto
Float Property Distance = 260.0 Auto

Event OnEffectStart(Actor akTarget, Actor akCaster)
	Float a = akCaster.GetAngleZ()
	AltairPortableHaystack.Disable()
	AltairPortableHaystack.MoveTo(akCaster, Distance * Math.Sin(a), Distance * Math.Cos(a), 0.0)
	AltairPortableHaystack.SetAngle(0.0, 0.0, a)
	AltairPortableHaystack.Enable()
	(AltairPortableHaystack as AltairHaystackScript).StartWatching()
EndEvent
