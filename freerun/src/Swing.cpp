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
			float        energy{ 0.0f };  // swing momentum, built up with W / S (AC1 pumps the swing)
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
		const Clip*  c = FindClip(a_clip);
		RE::NiPoint3 h = c ? c->HandsAt(a_u) : RE::NiPoint3{ 0.0f, 0.0f, 171.0f };
		h = h * ActorScale(RE::PlayerCharacter::GetSingleton());
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
		// the same spot the catch jump aimed at (the clip's first frame): no jump in position, so no camera kick
		HoldAt(a_player, SwingHangPosition(g.bar, g.facing, "swing_catch", 0.0f), YawOf(g.facing), false, true);
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

		// momentum: pushing W or S pumps the swing up (AC1), it dies away slowly when you stop
		if (std::abs(in.y) < 0.3f) {
			g.neutral = true;
		}
		if (g.neutral && std::abs(in.y) > 0.5f) {
			g.energy = std::min(1.0f, g.energy + 0.9f * a_delta);
		} else {
			g.energy = std::max(0.0f, g.energy - 0.2f * a_delta);
		}
		if (sprint) {
			g.energy = std::min(1.0f, g.energy + 0.6f * a_delta);  // free-run: he swings through by himself
		}
		// the cycle runs faster and swings wider with momentum: the still free hang blended with AC1's swing cycle
		const float d = ClipDuration("swing_loop", 1.77f);
		const float before = std::fmod(g.loopT, d) / d;
		g.loopT += a_delta * (0.45f + 0.55f * g.energy);
		const float u = std::fmod(g.loopT, d) / d;
		if (u < before) {
			++g.cycles;
		}
		const Clip* loop = FindClip("swing_loop");
		const Clip* hang = FindClip("swing_hang");
		if (loop && hang) {
			Blend b;
			b.parts.emplace_back(hang, 1.0f - g.energy);
			b.parts.emplace_back(loop, std::max(0.001f, g.energy));
			SetPose(b, u, 1.0f);
		}
		// the hands stay on the bar while the body swings under it
		const RE::NiPoint3 a = SwingHangPosition(g.bar, g.facing, "swing_hang", u);
		const RE::NiPoint3 c = SwingHangPosition(g.bar, g.facing, "swing_loop", u);
		HoldAt(a_player, a + (c - a) * g.energy, YawOf(g.facing), false, true);

		// let go and drop: sneak (AC1's "empty hand")
		if (TakeSneakPress()) {
			const RE::NiPoint3 drop = a - g.facing * (0.2f * U);
			HoldAt(a_player, drop, YawOf(g.facing), false, false);
			RestoreGravity(a_player);
			ClearPose();
			g.state = State::kNone;
			logger::info("swing: dropped");
			return;
		}
		// let go forward into a jump at the top of the forward swing, once there is some momentum
		if (ReadyToRelease(u) && g.energy > 0.35f && (jump || (sprint && g.energy > 0.7f))) {
			Release(a_player, !jump);
		}
	}
}
