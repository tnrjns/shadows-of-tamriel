#pragma once

// Shared helpers for the moves that hold the player themselves (beams, poles, swing bars, wall runs).

namespace Freerun
{
	constexpr float kUnitsPerMetre = 70.0f;

	// Put the player at a_at facing a_yaw. Re-places only when the spot really changed (re-placing every frame fights
	// the camera mods); a_floating turns the character controller's gravity off (restored by RestoreGravity).
	void HoldAt(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_at, float a_yaw, bool a_onGround, bool a_floating);
	void RestoreGravity(RE::PlayerCharacter* a_player);

	// Close out Skyrim's jump state in the behavior graph if a move started from a jump (JumpLand / End / FailSafe).
	void ResolveJumpState(RE::PlayerCharacter* a_player, float a_delta, float& a_clock);

	// The keys / stick as a horizontal world direction relative to the camera (length 0..1).
	RE::NiPoint3 InputWorld();

	float        YawOf(const RE::NiPoint3& a_dir);
	RE::NiPoint3 DirOf(float a_yaw);
	RE::NiPoint3 RightOf(const RE::NiPoint3& a_dir);

	// While an AC1 move runs, Skyrim's movement and jump controls are switched off: the keys still reach the plugin
	// (it reads them itself), but the game neither moves the player nor swings the camera round to follow input.
	void SetControlsLocked(bool a_locked);

	// The player's size (race height x reference scale): AC1 grip / hand offsets are scaled by it.
	float ActorScale(RE::PlayerCharacter* a_player);

	// A Skyrim sound by its editor id, at the player (e.g. the jump / landing footsteps).
	void PlaySoundAtPlayer(RE::PlayerCharacter* a_player, const char* a_editorID);

	// Play one clip at normalized time a_u (through PosePlayer).
	void PlayClip(const char* a_name, float a_u, float a_weight = 1.0f);
	float ClipDuration(const char* a_name, float a_fallback = 0.5f);
}
