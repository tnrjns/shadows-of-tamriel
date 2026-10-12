#include "Swing.h"
#include "EdgeFinder.h"
#include "Motion.h"
#include "Narrow.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		constexpr float U = kUnitsPerMetre;

		enum class State
		{
			kNone,
			kCatch,
			kSwing,
		};

		struct Swing
		{
			State        state{ State::kNone };
			RE::NiPoint3 bar;
			RE::NiPoint3 facing;
			float        t{ 0.0f };
			float        loopT{ 0.0f };
			float        jumpClock{ 0.0f };
			int          cycles{ 0 };
			bool         neutral{ false };  // keys let go since the catch (a key held from the run-up doesn't drop him)
		};
		Swing g;

		bool ReadyToRelease(float a_u)
		{
			// the end of the forward swing (front_up, the last part of the cycle): AC1 lets go at the top of it
			return a_u > 0.88f;
		}

		bool Release(RE::PlayerCharacter* a_player, bool a_auto)
		{
			a_player->data.angle.z = YawOf(g.facing);
			Update(a_player);
			const Snapshot snap = Latest();
			const Candidate* best = nullptr;
			for (const auto& c : snap.candidates) {
				if (c.inReach && c.distance > 1.0f && c.type != EdgeType::kBar && (!best || c.score > best->score)) {
					best = &c;
				}
			}
			if (!best) {
				return false;
			}
			if (!StartJumpFrom(a_player, best, "srelease")) {
				return false;
			}
			RestoreGravity(a_player);
			g.state = State::kNone;
			logger::info("swing: let go {}", a_auto ? "(free-run)" : "");
			return true;
		}
	}

	bool BarFrame(const RE::NiPoint3& a_point, const RE::NiPoint3& a_travel, RE::NiPoint3& a_axis, RE::NiPoint3& a_facing)
	{
		if (!BeamAxis(a_point, { -a_travel.y, a_travel.x, 0.0f }, a_axis)) {
			return false;
		}
		a_facing = { -a_axis.y, a_axis.x, 0.0f };
		if (a_facing.x * a_travel.x + a_facing.y * a_travel.y < 0.0f) {
			a_facing = a_facing * -1.0f;
		}
		return true;
	}

	RE::NiPoint3 SwingHangPosition(const RE::NiPoint3& a_bar, const RE::NiPoint3& a_facing, const char* a_clip, float a_u)
	{
		const Clip*        c = FindClip(a_clip);
		const RE::NiPoint3 h = c ? c->HandsAt(a_u) : RE::NiPoint3{ 0.0f, 0.0f, 164.0f };
		const RE::NiPoint3 grip = a_bar - RE::NiPoint3{ 0.0f, 0.0f, 0.04f * U };  // hands round the bar, under its top
		return grip - RightOf(a_facing) * h.x - a_facing * h.y - RE::NiPoint3{ 0.0f, 0.0f, h.z };
	}

	bool SwingActive() { return g.state != State::kNone; }

	void SwingBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_bar, const RE::NiPoint3& a_facing)
	{
		g = Swing{};
		g.bar = a_bar;
		g.facing = a_facing;
		g.state = State::kCatch;
		HoldAt(a_player, SwingHangPosition(g.bar, g.facing, "swing_catch", 1.0f), YawOf(g.facing), false, true);
		logger::info("swing: caught the bar at ({:.0f} {:.0f} {:.0f})", a_bar.x, a_bar.y, a_bar.z);
	}

	void SwingUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (g.state == State::kNone) {
			return;
		}
		g.t += a_delta;
		ResolveJumpState(a_player, a_delta, g.jumpClock);
		const bool         jump = TakeJumpPress();
		const RE::NiPoint2 in = RawMove();
		const bool         sprint = RawSprint() || a_player->AsActorState()->IsSprinting();

		if (g.state == State::kCatch) {
			const float d = ClipDuration("swing_catch", 0.2f);
			const float u = std::min(1.0f, g.t / d);
			PlayClip("swing_catch", u);
			HoldAt(a_player, SwingHangPosition(g.bar, g.facing, "swing_catch", u), YawOf(g.facing), false, true);
			if (u >= 1.0f) {
				g.state = State::kSwing;
				g.loopT = 0.0f;
			}
			return;
		}

		const float d = ClipDuration("swing_loop", 1.77f);
		const float before = std::fmod(g.loopT, d) / d;
		g.loopT += a_delta;
		const float u = std::fmod(g.loopT, d) / d;
		if (u < before) {
			++g.cycles;
		}
		PlayClip("swing_loop", u);
		// the hands stay on the bar while the body swings under it
		HoldAt(a_player, SwingHangPosition(g.bar, g.facing, "swing_loop", u), YawOf(g.facing), false, true);

		if (std::abs(in.x) < 0.3f && std::abs(in.y) < 0.3f) {
			g.neutral = true;
		}
		if (g.neutral && in.y < -0.5f) {
			const RE::NiPoint3 drop = SwingHangPosition(g.bar, g.facing, "swing_loop", 0.0f) - g.facing * (0.2f * U);
			HoldAt(a_player, drop, YawOf(g.facing), false, false);
			RestoreGravity(a_player);
			ClearPose();
			g.state = State::kNone;
			logger::info("swing: dropped");
			return;
		}
		if (ReadyToRelease(u) && (jump || (sprint && g.cycles >= 0 && g.loopT > d * 0.85f))) {
			Release(a_player, !jump);
		}
	}
}
