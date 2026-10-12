#pragma once

// AC1 viewpoint synchronization: at a leap point (the top of a tower, high over a haystack) the prayer key makes
// Altair perch in AC1's low beam crouch while the eagle cries and the camera sweeps once round him; then he is
// free to take the leap of faith. Moving after the first second ends it early.

namespace Freerun
{
	// Start a synchronization if the player stands at a leap point; false if not there (the key prays instead).
	bool SyncTry(RE::PlayerCharacter* a_player);
	void SyncUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool SyncActive();
}
