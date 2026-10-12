#pragma once

// AC1's blend prayer (xx_l_pray_wait: head bowed, hands together, as Altair blends in with the scholars) on a key.
// Press the key to ease into it, again (or move) to ease out. The player's eyes close while praying.

namespace Freerun
{
	void PrayKeyPressed();
	void PrayUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool PrayActive();
}
