#pragma once

// AC1-style jump candidates for Skyrim (plan: docs/AC1_FREERUN_PLAN.md, phase P0).
// AC1 reads hand-placed guidance edges; Skyrim has only collision, so the edges are found with Havok rays in front of
// the player, then classified and scored the way AC1's Human__QueryJumpCandidates / scorer 0xE96BF0 do (reference:
// AC1-Movement-Rewritten src/player/jump_candidates.rs).

namespace Freerun
{
	enum class EdgeType : std::uint8_t
	{
		kRoof,  // walkable top with room on it: free-step landing (AC1 type 1)
		kHang,  // a ledge with no standing room / out of landing reach: catch into a hang
		kBeam,  // narrow top with a drop on both sides
		kPole,  // narrow both ways: a pole top to perch on
		kBar,   // a thin bar above head height: caught with the hands and swung on
	};

	struct Candidate
	{
		RE::NiPoint3 point;      // grab / landing point on the edge (game units)
		RE::NiPoint3 wallNormal; // horizontal normal of the face below the edge, pointing back at the player
		EdgeType     type{ EdgeType::kRoof };
		float        distance{ 0.0f };  // horizontal, metres
		float        height{ 0.0f };    // above the feet, metres
		bool         inReach{ false };  // inside AC1's reach zone for this jump
		float        score{ 0.0f };
	};

	struct Snapshot
	{
		std::vector<Candidate> candidates;
		int                    chosen{ -1 };
		RE::NiPoint3           origin;
	};

	// Probe the world in front of the player and rebuild the candidate list (main thread).
	void Update(RE::PlayerCharacter* a_player);

	// Copy of the latest result (any thread).
	Snapshot Latest();

	// One static-world Havok ray (game units). Returns false when nothing was hit.
	bool CastRay(const RE::NiPoint3& a_from, const RE::NiPoint3& a_to, RE::NiPoint3* a_hit = nullptr, RE::NiPoint3* a_normal = nullptr);

	// Is there ground within a_drop metres below the point a_ahead metres in front of the feet? (free-run edge test)
	bool GroundAhead(RE::PlayerCharacter* a_player, float a_ahead, float a_drop);

	// AC1's 13 side-profile reach zones, (horizontal distance m, height above feet m).
	bool InZone(int a_slot, float a_distance, float a_height);
}
