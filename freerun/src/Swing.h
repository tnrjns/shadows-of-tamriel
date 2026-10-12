#pragma once

// P4: swing bars, after AC1's swing (HumanSwing; AC1-Movement-Rewritten src/player/swing.rs). A jump at a thin
// horizontal bar above head height catches it with AC1's "to swing" flight; he swings through AC1's swing cycle
// with his hands kept on the bar, and lets go forward into a jump to the next target (jump, or by itself when
// sprinting); S drops.

namespace Freerun
{
	// The bar's line through a_point and the facing across it (toward a_travel).
	bool BarFrame(const RE::NiPoint3& a_point, const RE::NiPoint3& a_travel, RE::NiPoint3& a_axis, RE::NiPoint3& a_facing);

	// Where the feet go so the hands of a_clip (at time a_u) are on the bar.
	RE::NiPoint3 SwingHangPosition(const RE::NiPoint3& a_bar, const RE::NiPoint3& a_facing, const char* a_clip, float a_u);

	void SwingBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_bar, const RE::NiPoint3& a_facing);
	void SwingUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool SwingActive();
}
