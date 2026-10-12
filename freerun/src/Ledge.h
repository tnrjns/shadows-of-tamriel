#pragma once

// P3: ledges, after AC1's ledge context (HumanLedge, RE/03 §7; AC1-Movement-Rewritten src/player/ledge.rs).
// A jump at an edge too high to land on catches it into a wall hang. While hanging: A / D shimmies along the edge
// in AC1's 0.5 m hand-over-hand steps (only where the edge and the wall below it go on), W pulls up onto the top
// (only with room to stand there; holding sprint goes straight into a run), S lets go.
// Positions come from AC1's own clips: the hands of the hang pose are put on the edge.

namespace Freerun
{
	// Start hanging on the edge at a_edge (top of the ledge, game units), the player facing a_facing (horizontal).
	// a_fromJump: Skyrim's jump state may still be running in the behavior graph.
	void LedgeBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing);

	// Where the player's feet go to hang from a_edge facing a_facing (for aiming the catch jump).
	RE::NiPoint3 LedgeHangPosition(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing);

	// Snap a candidate edge to the real wall face and top (returns false if there is no wall to hang from).
	bool LedgeRefine(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing, RE::NiPoint3& a_outEdge, RE::NiPoint3& a_outFacing);

	void LedgeUpdate(RE::PlayerCharacter* a_player, float a_delta);
	bool LedgeActive();
}
