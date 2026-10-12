#pragma once

// P4: beams and poles, after AC1's narrow-object context (HumanNarrowObject, RE/05 §2; AC1-Movement-Rewritten
// src/player/narrow.rs). Landing on a beam: Altair crouches into AC1's balance walk, kept on the beam's line
// (forward along it walks, held sprint jogs, back turns him round), stops 0.3 m before an end, steps off an end
// with free space beyond it, and jumps on to the next target (by itself when sprinting off the end).
// On a pole top he perches and hops to the next target in the direction you push.

namespace Freerun
{
	// Find a beam's line through a_point (on its top): a horizontal unit axis, false if the top is not long
	// (then it is a pole top).
	bool BeamAxis(const RE::NiPoint3& a_point, const RE::NiPoint3& a_near, RE::NiPoint3& a_axis);

	void NarrowBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_point, const RE::NiPoint3& a_travel, bool a_pole);
	void NarrowUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool NarrowActive();
}
