#pragma once

// P2: plays AC1 clips on the player's third-person skeleton, outside the behavior graph (like FreeClimb / Faith
// Runner's Body): the clips are AC1 takeoffs / flights / receptions retargeted offline to the Skyrim skeleton
// (tools/retarget_ac1_v2.py, ALTAIR_JOBSET=freerun) and packed by tools/pack_freerun.py.

namespace Freerun
{
	struct Clip
	{
		std::string                         name;
		float                               duration{ 0.0f };
		std::uint32_t                       frames{ 0 };
		std::vector<RE::NiQuaternion>       rot;   // frames x bones
		std::vector<RE::NiPoint3>           trans; // frames x bones
		std::vector<std::array<float, 2>>   disp;  // frames: AC1 root displacement (forward, up), metres
		std::vector<RE::NiPoint3>           hands; // frames: midpoint of the hands, actor space (x right, y fwd, z up)
		std::vector<float>                  yaw;   // frames: AC1 root heading from frame 0, radians (+ = right)
		std::array<float, 2>                DispAt(float a_u) const;
		RE::NiPoint3                        HandsAt(float a_u) const;
		float                               YawAt(float a_u) const;
	};

	// A weighted set of clips played at the same normalized time (AC1 blends its jump items by distance/height).
	struct Blend
	{
		std::vector<std::pair<const Clip*, float>> parts;
		float                                      Duration() const;
		std::array<float, 2>                       DispAt(float a_u) const;
		float                                      YawAt(float a_u) const;
		bool                                       Empty() const { return parts.empty(); }
	};

	bool        LoadPack();                     // Data/SKSE/Plugins/AltairFreerun/AltairFreerun.pack
	const Clip* FindClip(const std::string& a_name);

	// What the pose player shows this frame (set by the jump state machine).
	void SetPose(const Blend& a_blend, float a_u, float a_weight);
	void ClearPose();

	// Animation hook: write the pose onto the player's skeleton after Skyrim's animation update.
	void ApplyPose(RE::PlayerCharacter* a_player, float a_delta);

	// Gait smoothing: when the player switches walk / run / sprint, the pose change Skyrim makes is eased out over
	// a_seconds (inertialization: the pose jump at the switch is captured as an offset that decays). 0 = off.
	void SetGaitSmoothing(float a_seconds);
}
