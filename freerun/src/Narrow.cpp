#include "Narrow.h"
#include "EdgeFinder.h"
#include "Motion.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		constexpr float U = kUnitsPerMetre;
		constexpr float kEndMargin = 0.3f;  // AC1 stops 0.3 m before a beam end (ConstrainRootMotionToBeam)

		enum class State
		{
			kNone,
			kLand,
			kWait,
			kWalk,
			kTurn,
		};

		struct Narrow
		{
			State        state{ State::kNone };
			bool         pole{ false };
			RE::NiPoint3 origin;           // a point on the beam's top line
			RE::NiPoint3 axis{ 0.0f, 1.0f, 0.0f };
			float        s{ 0.0f };        // position along the axis (game units)
			float        sMin{ 0.0f }, sMax{ 0.0f };
			float        facing{ 1.0f };   // +1 / -1 along the axis (beam); pole: yaw below
			float        poleYaw{ 0.0f };
			float        t{ 0.0f };
			float        loopT{ 0.0f };
			float        atEnd{ 0.0f };    // time spent pushing at an end
			float        jumpClock{ 0.0f };
			bool         jog{ false };
		};
		Narrow g;

		float TopAt(const RE::NiPoint3& a_p, float a_z, bool* a_hit)
		{
			RE::NiPoint3 hit;
			const bool   h = CastRay({ a_p.x, a_p.y, a_z + 0.3f * U }, { a_p.x, a_p.y, a_z - 0.3f * U }, &hit);
			if (a_hit) {
				*a_hit = h && std::abs(hit.z - a_z) < 0.12f * U;
			}
			return h ? hit.z : a_z;
		}

		RE::NiPoint3 PointAt(float a_s)
		{
			RE::NiPoint3 p = g.origin + g.axis * a_s;
			bool         hit = false;
			p.z = TopAt(p, g.origin.z, &hit) + 1.0f;
			return p;
		}

		float Yaw() { return g.pole ? g.poleYaw : YawOf(g.axis * g.facing); }

		void Hold(RE::PlayerCharacter* a_player)
		{
			// held still with gravity off: on a 40 cm pole top (or a beam) the character controller would keep sliding
			// off the edge and be pulled back every frame
			HoldAt(a_player, PointAt(g.s), Yaw(), true, true);
		}

		// jump on from the beam / pole to the best target in the facing direction (AC1: free-step jump, kind 1)
		bool JumpOn(RE::PlayerCharacter* a_player, bool a_auto)
		{
			a_player->data.angle.z = Yaw();
			Update(a_player);
			const Snapshot snap = Latest();
			const Candidate* best = nullptr;
			for (const auto& c : snap.candidates) {
				if (c.inReach && c.distance > 0.8f && (!best || c.score > best->score)) {
					best = &c;
				}
			}
			if (!best || (a_auto && best->type == EdgeType::kHang && !GetSettings().ledges)) {
				return false;
			}
			if (!StartJumpFrom(a_player, best, "btakeoff")) {
				return false;
			}
			RestoreGravity(a_player);
			g.state = State::kNone;
			logger::info("{}: jumped on", g.pole ? "pole" : "beam");
			return true;
		}

		void Leave(RE::PlayerCharacter* a_player, const char* a_why)
		{
			g.state = State::kNone;
			RestoreGravity(a_player);
			ClearPose();
			logger::info("{}: {}", g.pole ? "pole" : "beam", a_why);
		}

		// jump with no target in front: a small hop off forward (AC1 jumps off into the drop)
		void HopOff(RE::PlayerCharacter* a_player)
		{
			const RE::NiPoint3 f = DirOf(Yaw());
			HoldAt(a_player, PointAt(g.s) + f * (0.35f * U) + RE::NiPoint3{ 0.0f, 0.0f, 0.1f * U }, Yaw(), false, false);
			Leave(a_player, "hopped off");
			if (auto* controller = a_player->GetCharController()) {
				const float s = U * RE::bhkWorld::GetWorldScale();
				controller->SetLinearVelocityImpl(RE::hkVector4(f.x * 3.0f * s, f.y * 3.0f * s, 3.0f * s, 0.0f));
			}
		}
	}

	bool BeamAxis(const RE::NiPoint3& a_point, const RE::NiPoint3& a_near, RE::NiPoint3& a_axis)
	{
		// the direction (in 15 degree steps) in which the top goes on 0.5 m both ways; nearest to a_near wins
		float best = -2.0f;
		bool  found = false;
		for (int i = 0; i < 12; ++i) {
			const float        a = static_cast<float>(i) * RE::NI_PI / 12.0f;
			const RE::NiPoint3 d{ std::sin(a), std::cos(a), 0.0f };
			bool               h1 = false, h2 = false;
			TopAt(a_point + d * (0.5f * U), a_point.z, &h1);
			TopAt(a_point - d * (0.5f * U), a_point.z, &h2);
			if (h1 && h2) {
				const float score = std::abs(d.x * a_near.x + d.y * a_near.y);
				if (score > best) {
					best = score;
					a_axis = d;
					found = true;
				}
			}
		}
		return found;
	}

	bool NarrowActive() { return g.state != State::kNone; }

	void NarrowTryWalkOn(RE::PlayerCharacter* a_player)
	{
		auto* controller = a_player->GetCharController();
		if (!controller || controller->context.currentState != RE::hkpCharacterStateType::kOnGround || LeapArmed(a_player)) {
			return;  // at a leap point the plank is for the leap of faith, not a balance walk
		}
		const RE::NiPoint3 feet = a_player->GetPosition();
		const RE::NiPoint3 fwd = DirOf(a_player->data.angle.z);
		const RE::NiPoint3 right = RightOf(fwd);
		auto support = [&](const RE::NiPoint3& a_p) {
			RE::NiPoint3 hit;
			return CastRay(a_p + RE::NiPoint3{ 0.0f, 0.0f, 0.3f * U }, a_p - RE::NiPoint3{ 0.0f, 0.0f, 0.6f * U }, &hit) &&
			       hit.z > feet.z - 0.35f * U;
		};
		if (!support(feet)) {
			return;
		}
		const bool across = !support(feet + right * (0.35f * U)) && !support(feet - right * (0.35f * U));
		if (!across) {
			return;  // ground either side: not on a beam
		}
		const bool along = !support(feet + fwd * (0.35f * U)) && !support(feet - fwd * (0.35f * U));
		RE::NiPoint3 top;
		CastRay(feet + RE::NiPoint3{ 0.0f, 0.0f, 0.3f * U }, feet - RE::NiPoint3{ 0.0f, 0.0f, 0.6f * U }, &top);
		NarrowBegin(a_player, { feet.x, feet.y, top.z }, fwd, along, false);
	}

	void NarrowBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_point, const RE::NiPoint3& a_travel, bool a_pole, bool a_land)
	{
		g = Narrow{};
		g.pole = a_pole;
		g.origin = a_point;
		RE::NiPoint3 travel{ a_travel.x, a_travel.y, 0.0f };
		const float  tl = std::sqrt(travel.x * travel.x + travel.y * travel.y);
		travel = tl > 0.01f ? travel / tl : DirOf(a_player->data.angle.z);
		if (!a_pole && !BeamAxis(a_point, travel, g.axis)) {
			g.pole = true;
		}
		g.poleYaw = YawOf(travel);
		if (!g.pole) {
			g.facing = (travel.x * g.axis.x + travel.y * g.axis.y) >= 0.0f ? 1.0f : -1.0f;
			// the ends: walk the top both ways until it stops
			for (int dir : { 1, -1 }) {
				float s = 0.0f;
				for (int k = 0; k < 80; ++k) {
					bool hit = false;
					TopAt(g.origin + g.axis * ((s + dir * 0.25f * U)), g.origin.z, &hit);
					if (!hit) {
						break;
					}
					s += dir * 0.25f * U;
				}
				(dir > 0 ? g.sMax : g.sMin) = s;
			}
		}
		g.state = a_land ? State::kLand : State::kWait;
		g.t = 0.0f;
		Hold(a_player);
		logger::info("{}: landed ({:.1f} m long)", g.pole ? "pole" : "beam", (g.sMax - g.sMin) / U);
	}

	void NarrowUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (g.state == State::kNone) {
			return;
		}
		g.t += a_delta;
		ResolveJumpState(a_player, a_delta, g.jumpClock);
		const bool         jump = TakeJumpPress();
		const bool         sprint = RawSprint() || a_player->AsActorState()->IsSprinting();
		const RE::NiPoint3 in = InputWorld();
		const float        push = std::sqrt(in.x * in.x + in.y * in.y);

		// at a leap point: hand back to Skyrim so its jump does the leap of faith
		if (LeapArmed(a_player)) {
			Leave(a_player, "leap point - free for the leap of faith");
			return;
		}
		// fell off (pushed, knocked down...)
		auto* controller = a_player->GetCharController();
		if (controller && a_player->GetPosition().z < g.origin.z - 0.8f * U) {
			Leave(a_player, "fell off");
			return;
		}

		if (g.pole) {
			// perched: face where you push; hop on with jump, or by itself when sprinting toward a target
			if (g.state == State::kLand) {
				const float d = ClipDuration("pole_land", 0.7f);
				PlayClip("pole_land", g.t / d);
				if (g.t >= d) {
					g.state = State::kWait;
				}
			} else {
				g.loopT += a_delta;
				const float d = ClipDuration("pole_wait", 2.0f);
				PlayClip("pole_wait", std::fmod(g.loopT, d) / d);
			}
			if (push > 0.5f) {
				// turn toward where you push, smoothly (not a snap every frame as the camera moves)
				const float want = YawOf(in);
				float       diff = std::fmod(want - g.poleYaw + 3.0f * RE::NI_PI, 2.0f * RE::NI_PI) - RE::NI_PI;
				if (std::abs(diff) > 0.15f) {
					const float step = 6.0f * a_delta;
					g.poleYaw += std::clamp(diff, -step, step);
				}
			}
			Hold(a_player);
			if (g.state != State::kLand && (jump || (sprint && push > 0.5f && g.t > 0.4f))) {
				if (!JumpOn(a_player, !jump) && jump) {
					HopOff(a_player);
				}
			}
			return;
		}

		const float along = (in.x * g.axis.x + in.y * g.axis.y) * g.facing;  // + forward along the beam, - back
		switch (g.state) {
		case State::kLand:
			{
				// AC1's free-step entry onto the beam carries him a little way along it
				const float d = ClipDuration("beam_land", 0.73f);
				const float u = std::min(1.0f, g.t / d);
				const Clip* c = FindClip("beam_land");
				const float step = c ? c->DispAt(u)[0] - c->DispAt(std::max(0.0f, (g.t - a_delta) / d))[0] : 0.0f;
				g.s = std::clamp(g.s + g.facing * step * U, g.sMin + kEndMargin * U, g.sMax - kEndMargin * U);
				PlayClip("beam_land", u);
				Hold(a_player);
				if (u >= 1.0f) {
					g.state = State::kWait;
					g.loopT = 0.0f;
				}
				break;
			}
		case State::kWait:
		case State::kWalk:
			{
				if (jump) {
					if (!JumpOn(a_player, false)) {
						HopOff(a_player);
					}
					return;
				}
				if (along < -0.5f) {
					g.state = State::kTurn;
					g.t = 0.0f;
					break;
				}
				const bool  moving = along > 0.4f;
				const bool  jog = moving && sprint;
				const char* clip = moving ? (jog ? "beam_jog" : "beam_walk") : "beam_wait";
				if (moving) {
					// speed from the clip's own stride (AC1 moves on a beam by its root motion along the beam)
					const Clip* c = FindClip(clip);
					const float speed = c && c->duration > 0.0f ? c->DispAt(1.0f)[0] / c->duration : 1.4f;
					const float limit = g.facing > 0.0f ? g.sMax - kEndMargin * U : g.sMin + kEndMargin * U;
					g.s += g.facing * speed * U * a_delta;
					const bool atEnd = g.facing > 0.0f ? g.s >= limit : g.s <= limit;
					if (atEnd) {
						g.s = limit;
						g.atEnd += a_delta;
						// sprinting off the end: on to the next target by itself (AC1 free-run); else step off it
						if (jog && JumpOn(a_player, true)) {
							return;
						}
						if (g.atEnd > 0.35f) {
							const RE::NiPoint3 off = PointAt(g.s) + g.axis * (g.facing * 0.45f * U);
							HoldAt(a_player, off, Yaw(), false, false);
							Leave(a_player, "stepped off the end");
							return;
						}
					} else {
						g.atEnd = 0.0f;
					}
					g.state = State::kWalk;
				} else {
					g.state = State::kWait;
					g.atEnd = 0.0f;
				}
				g.loopT += a_delta;
				const float d = ClipDuration(clip, 1.0f);
				PlayClip(clip, std::fmod(g.loopT, d) / d);
				Hold(a_player);
				break;
			}
		case State::kTurn:
			{
				const float d = ClipDuration("beam_turn", 0.53f);
				PlayClip("beam_turn", std::min(1.0f, g.t / d));
				Hold(a_player);
				if (g.t >= d) {
					g.facing = -g.facing;  // the clip turns him round
					g.state = State::kWait;
					g.loopT = 0.0f;
				}
				break;
			}
		default:
			break;
		}
	}
}
