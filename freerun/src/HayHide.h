#pragma once

// Hiding in a haystack, as in AC1: a leap of faith into one of AltairLeapOfFaith.esp's haystacks (an AC1-sized
// haystack without collision) sinks Altair into it with AC1's air-to-haystack dive, he waits hidden inside
// (xx_h_haystack_wait), and moving or jumping hops him out (xx_l_haystack_hop_out) in that direction.

namespace Freerun
{
	void HayUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool HayActive();
}
