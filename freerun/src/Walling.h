#pragma once

// P4: the wall run up, after AC1's HumanWalling (RE/05 §1; AC1-Movement-Rewritten src/player/walling.rs). Jump at
// a wall too tall to catch from the ground: Altair runs up it (AC1's wallingfront entry + step), and catches the
// top with AC1's walling-to-hang clip when it is within reach (up to about 5 m above the feet); otherwise he
// pushes off and falls back.

namespace Freerun
{
	// Try to start a wall run at the wall in front of the player. False when there is no suitable wall.
	bool WallRunTry(RE::PlayerCharacter* a_player);
	void WallRunUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool WallRunActive();
}
