#pragma once

#include "EdgeFinder.h"

// P1: target-locked jumps. AC1 jumps are not ballistic: the jump is set up toward the chosen target and the root is
// corrected over the flight so it arrives exactly there (Human__SetupJumpToTarget 0xB20200 / HumanInAir__
// UpdateJumpMotion 0xE0DEF0). Until the AC1 clips are played by our own pose player (P2), the flight path is an arc
// timed like AC1's jump items. P2: AC1's own takeoff / flight / reception clips play through PosePlayer and the
// root follows their displacement plus AC1's linear correction.

namespace Freerun
{
	struct Settings
	{
		bool  overlay{ true };       // draw the candidate markers
		bool  targetJumps{ true };   // take over the jump when there is a target
		bool  requireSprint{ true }; // AC1: free-run jumps need high profile (sprint)
		bool  ac1Animations{ true }; // P2: play AC1's takeoff / flight / reception clips
		bool  autoJump{ true };      // AC1 free-run: sprinting off an edge (or at a step up) jumps to the target by itself
		bool  ledges{ true };        // P3: catch ledges that are too high to land on, hang / shimmy / pull up / drop
		bool  p4{ true };            // P4: beams (balance walk), poles, swing bars, wall run up
		bool  hayHide{ true };       // leap of faith into a haystack: hide inside it, hop out
		float gaitSmoothing{ 0.0f }; // seconds; eases the pose change when switching walk / run / sprint
		bool  pray{ true };          // AC1 blend prayer on a key
		bool  prayCloseEyes{ true }; // the player's eyes close while praying
		int   prayKey{ 0x30 };       // DirectInput scan code (0x30 = B)
		float arcHeight{ 1.0f };     // scale on the flight arc
		void  Load();
		void  Save() const;
	};
	Settings& GetSettings();

	// Called every frame from the player update hook, after Skyrim's own update.
	void TargetJumpUpdate(RE::PlayerCharacter* a_player, float a_delta);

	// Movement keys / left stick as pressed (x right, y forward), before True Directional Movement turns every
	// direction into "forward": hanging on a ledge needs the real left / right.
	void         SetRawMove(int a_axis, float a_value);   // 0 forward, 1 back, 2 left, 3 right (keys); 4 / 5 stick x / y
	RE::NiPoint2 RawMove();

	// SkyParkour: abort its own climb / vault if it started on the same jump press as one of our moves.
	void SuppressSkyParkour(RE::PlayerCharacter* a_player, float a_delta);

	// The jump key press of this frame, taken by whichever move uses it (beam, pole, swing take it first).
	bool TakeJumpPress();
	// The sneak key press (lets go of a swing bar, AC1's empty hand).
	void NotifySneakPressed();
	bool TakeSneakPress();
	void SetRawSprint(bool a_down);
	bool RawSprint();

	// Jump from wherever the player is (beam, pole, swing bar) to a_target, with the takeoff clips a_takeoff
	// ("takeoff" from a run, "btakeoff" a free-step from a beam / pole, "srelease" letting go of a swing bar).
	bool StartJumpFrom(RE::PlayerCharacter* a_player, const Candidate* a_target, const char* a_takeoff);

	// The jump key went down this frame (from the input sink; reacts before mods that climb on the jump key).
	void NotifyJumpPressed();

	// True while a target jump is moving the player.
	bool TargetJumpActive();
	// True from the takeoff until the landing (reception) has finished: the player's controls stay locked.
	bool TargetJumpBusy();
	// True while AltairLeapOfFaith.esp has armed the dive (standing at a leap point): Skyrim's own jump does the leap.
	bool LeapArmed(RE::PlayerCharacter* a_player);
}
