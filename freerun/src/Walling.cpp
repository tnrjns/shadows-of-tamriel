#include "Walling.h"
#include "EdgeFinder.h"
#include "Ledge.h"
#include "Motion.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		constexpr float U = kUnitsPerMetre;
		constexpr float kMaxTop = 5.2f;  // highest top (above the feet) the run up can catch

		struct WallRun
		{
			bool         active{ false };
			bool         toHang{ false };
			RE::NiPoint3 from;
			RE::NiPoint3 to;        // the hang position (or where the run up tops out)
			RE::NiPoint3 facing;
			RE::NiPoint3 edge;
			const char*  second{ "wall_fall" };
			float        t1{ 0.0f }, t2{ 0.0f }, t{ 0.0f };
			std::array<float, 2> endDisp{ 0.0f, 0.0f };
			float        jumpClock{ 0.0f };
		};
		WallRun g;

		std::array<float, 2> Disp(const char* a_clip, float a_u)
		{
			const Clip* c = FindClip(a_clip);
			return c ? c->DispAt(a_u) : std::array<float, 2>{ 0.0f, 0.0f };
		}
	}

	bool WallRunActive() { return g.active; }

	bool WallRunTry(RE::PlayerCharacter* a_player)
	{
		const RE::NiPoint3 feet = a_player->GetPosition();
		const RE::NiPoint3 fwd = DirOf(a_player->data.angle.z);
		// a wall straight ahead at waist and head height, within 1.6 m, facing back at us
		RE::NiPoint3 hit, normal, hit2;
		const RE::NiPoint3 waist = feet + RE::NiPoint3{ 0.0f, 0.0f, 0.9f * U };
		if (!CastRay(waist, waist + fwd * (1.6f * U), &hit, &normal) ||
			!CastRay(waist + RE::NiPoint3{ 0.0f, 0.0f, 1.0f * U }, waist + RE::NiPoint3{ 0.0f, 0.0f, 1.0f * U } + fwd * (1.8f * U), &hit2)) {
			return false;
		}
		RE::NiPoint3 n{ normal.x, normal.y, 0.0f };
		const float  nl = std::sqrt(n.x * n.x + n.y * n.y);
		if (nl < 0.8f || (n.x * fwd.x + n.y * fwd.y) / nl > -0.8f) {
			return false;  // not upright, or not square-on enough (AC1: within ~35 degrees)
		}
		const RE::NiPoint3 facing = n / -nl;
		// its top: a down ray just inside the wall from high up
		const RE::NiPoint3 in = hit + facing * (0.2f * U);
		RE::NiPoint3       top;
		const bool         hasTop = CastRay({ in.x, in.y, feet.z + 6.5f * U }, { in.x, in.y, feet.z + 2.0f * U }, &top);
		const float        h = hasTop ? (top.z - feet.z) / U : 99.0f;
		if (hasTop && h < 3.1f) {
			return false;  // low enough to catch from a jump (the ledge catch handles it)
		}

		g = WallRun{};
		g.facing = facing;
		g.from = feet;
		g.t1 = ClipDuration("wall_entry", 0.33f);
		if (hasTop && h <= kMaxTop && LedgeRefine({ hit.x, hit.y, top.z }, facing, g.edge, g.facing)) {
			g.toHang = true;
			g.second = h < 3.6f ? "wall_hang_250" : "wall_hang_430";
			g.to = LedgeHangPosition(g.edge, g.facing);
		} else {
			// too tall: run up as far as the entry goes, then push off and fall back (AC1's walling to fall)
			g.second = "wall_fall";
			const auto e = Disp("wall_entry", 1.0f);
			const RE::NiPoint3 wallFoot = hit - facing * (0.35f * U);
			g.to = RE::NiPoint3{ wallFoot.x, wallFoot.y, feet.z + e[1] * U };
		}
		g.t2 = g.toHang ? ClipDuration(g.second, 0.5f) : 0.0f;
		const auto a = Disp("wall_entry", 1.0f);
		const auto b = g.toHang ? Disp(g.second, 1.0f) : std::array<float, 2>{ 0.0f, 0.0f };
		g.endDisp = { a[0] + b[0], a[1] + b[1] };
		g.active = true;
		g.t = 0.0f;
		logger::info("wall run: top {:.1f} m up -> {}", h, g.toHang ? g.second : "push off");
		return true;
	}

	void WallRunUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (!g.active) {
			return;
		}
		g.t += a_delta;
		ResolveJumpState(a_player, a_delta, g.jumpClock);
		const float T = g.t1 + g.t2;
		const float s = std::min(1.0f, g.t / T);
		// AC1's root motion up the wall plus the linear correction onto the hang (AC1 walling uses the clips' motion)
		std::array<float, 2> d;
		if (g.t < g.t1) {
			d = Disp("wall_entry", g.t / g.t1);
			PlayClip("wall_entry", g.t / g.t1);
		} else {
			const auto a = Disp("wall_entry", 1.0f);
			const auto b = g.t2 > 0.0f ? Disp(g.second, (g.t - g.t1) / g.t2) : std::array<float, 2>{ 0.0f, 0.0f };
			d = { a[0] + b[0], a[1] + b[1] };
			if (g.t2 > 0.0f) {
				PlayClip(g.second, (g.t - g.t1) / g.t2);
			}
		}
		const RE::NiPoint3 anim = g.from + g.facing * (d[0] * U) + RE::NiPoint3{ 0.0f, 0.0f, d[1] * U };
		const RE::NiPoint3 animEnd = g.from + g.facing * (g.endDisp[0] * U) + RE::NiPoint3{ 0.0f, 0.0f, g.endDisp[1] * U };
		HoldAt(a_player, anim + (g.to - animEnd) * s, YawOf(g.facing), false, true);
		if (s < 1.0f) {
			return;
		}
		g.active = false;
		RestoreGravity(a_player);
		if (g.toHang) {
			LedgeBegin(a_player, g.edge, g.facing);
		} else {
			// push off: back from the wall and let Skyrim's fall take over, AC1's fall-from-wall fading out
			HoldAt(a_player, g.to - g.facing * (0.3f * U), YawOf(g.facing), false, false);
			ClearPose();
			logger::info("wall run: pushed off");
		}
	}
}
