#include "Ledge.h"
#include "EdgeFinder.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		constexpr float kUnits = 70.0f;
		constexpr float kStep = 0.5f;  // AC1 shimmy: hangwall_strafe_*_050cm

		enum class State
		{
			kNone,
			kCatch,
			kHang,
			kShimmy,
			kPullUp,
			kDrop,
		};

		struct Ledge
		{
			State        state{ State::kNone };
			RE::NiPoint3 edge;       // on the top, at the wall face
			RE::NiPoint3 facing;     // horizontal, into the wall
			float        t{ 0.0f };
			const Clip*  clip{ nullptr };
			RE::NiPoint3 from;       // feet at the start of a move
			RE::NiPoint3 to;         // feet at its end
			RE::NiPoint3 edgeFrom, edgeTo;
			int          shimmyDir{ 0 };
			bool         openHands{ true };  // AC1 alternates open / close shimmy steps
			float        jumpClock{ 0.0f };   // resolving Skyrim's jump state while hanging
			bool         neutral{ false };    // the stick has come back to the centre since the catch
		};
		Ledge g;

		const Clip* C(const char* a_name) { return FindClip(a_name); }

		RE::NiPoint3 Right(const RE::NiPoint3& f) { return { f.y, -f.x, 0.0f }; }

		float Yaw(const RE::NiPoint3& f) { return std::atan2(f.x, f.y); }

		float g_savedGravity = -1.0f;

		void Gravity(RE::PlayerCharacter* a_player, bool a_on)
		{
			auto* controller = a_player->GetCharController();
			if (!controller) {
				return;
			}
			if (!a_on && g_savedGravity < 0.0f) {
				g_savedGravity = controller->gravity;
				controller->gravity = 0.0f;
			} else if (a_on && g_savedGravity >= 0.0f) {
				controller->gravity = g_savedGravity;
				g_savedGravity = -1.0f;
			}
		}

		void Hold(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_at, bool a_onGround)
		{
			// re-place only when the spot really changed (re-placing every frame fights the camera mods)
			if (a_player->GetPosition().GetDistance(a_at) > 0.5f) {
				a_player->SetPosition(a_at, true);
			}
			const float yaw = Yaw(g.facing);
			float       dy = std::fmod(a_player->data.angle.z - yaw + 3.0f * RE::NI_PI, 2.0f * RE::NI_PI) - RE::NI_PI;
			if (std::abs(dy) > 0.01f) {
				a_player->data.angle.z = yaw;
			}
			Gravity(a_player, false);
			if (auto* controller = a_player->GetCharController()) {
				controller->SetLinearVelocityImpl(RE::hkVector4(0.0f, 0.0f, 0.0f, 0.0f));
				controller->fallStartHeight = a_at.z;
				controller->fallTime = 0.0f;
				if (a_onGround) {
					controller->context.currentState = RE::hkpCharacterStateType::kOnGround;
					controller->flags.set(RE::CHARACTER_FLAGS::kSupport);
				} else {
					controller->context.currentState = RE::hkpCharacterStateType::kInAir;
				}
			}
		}

		void Play(const Clip* a_clip, float a_u, float a_weight = 1.0f)
		{
			if (!a_clip) {
				return;
			}
			Blend b;
			b.parts.emplace_back(a_clip, 1.0f);
			SetPose(b, a_u, a_weight);
		}

		// Is there room to stand on top of the ledge, a little in from the edge?
		bool RoomOnTop(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing)
		{
			const RE::NiPoint3 p = a_edge + a_facing * (0.45f * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, 0.1f * kUnits };
			RE::NiPoint3       floorHit;
			const bool floor = CastRay(p + RE::NiPoint3{ 0.0f, 0.0f, 0.3f * kUnits }, p - RE::NiPoint3{ 0.0f, 0.0f, 0.4f * kUnits }, &floorHit);
			const bool head = CastRay(p, p + RE::NiPoint3{ 0.0f, 0.0f, 1.75f * kUnits });
			return floor && !head;
		}

		// Does the edge go on a_dir * 0.5 m (same top height, wall still under it, nothing in the way of the hands)?
		bool CanShimmy(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing, int a_dir, RE::NiPoint3& a_next)
		{
			const RE::NiPoint3 side = Right(a_facing) * static_cast<float>(a_dir);
			const RE::NiPoint3 n = a_edge + side * (kStep * kUnits);
			RE::NiPoint3       top;
			if (!CastRay(n + a_facing * (0.15f * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, 0.3f * kUnits },
					n + a_facing * (0.15f * kUnits) - RE::NiPoint3{ 0.0f, 0.0f, 0.3f * kUnits }, &top) ||
				std::abs(top.z - a_edge.z) > 0.15f * kUnits) {
				return false;
			}
			const RE::NiPoint3 low = n - RE::NiPoint3{ 0.0f, 0.0f, 0.35f * kUnits };
			if (!CastRay(low - a_facing * (0.5f * kUnits), low + a_facing * (0.3f * kUnits))) {
				return false;  // no wall under the hands
			}
			// the hands' path along the wall is clear (no wall across the ledge)
			const RE::NiPoint3 hand = a_edge - a_facing * (0.2f * kUnits) - RE::NiPoint3{ 0.0f, 0.0f, 0.15f * kUnits };
			if (CastRay(hand, hand + side * ((kStep + 0.25f) * kUnits))) {
				return false;
			}
			a_next = { n.x, n.y, top.z };
			return true;
		}

		// Skyrim's jump may still be running in the behavior graph (the catch came from a jump): close it out
		void ResolveJump(RE::PlayerCharacter* a_player, float a_delta)
		{
			bool inJump = false;
			a_player->GetGraphVariableBool("bInJumpState", inJump);
			if (!inJump) {
				g.jumpClock = 0.0f;
				return;
			}
			const float before = g.jumpClock;
			g.jumpClock += a_delta;
			if (before < 0.2f && g.jumpClock >= 0.2f) {
				a_player->NotifyAnimationGraph("JumpLand");
			} else if (before < 0.6f && g.jumpClock >= 0.6f) {
				a_player->NotifyAnimationGraph("JumpLandEnd");
			} else if (before < 1.0f && g.jumpClock >= 1.0f) {
				a_player->NotifyAnimationGraph("JumpLandFailSafe");
			}
		}

		RE::NiPoint2 MoveInput()
		{
			return RawMove();  // the keys / stick themselves (TDM turns every direction into forward)
		}
	}

	RE::NiPoint3 LedgeHangPosition(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing)
	{
		const Clip*        wait = C("hang_wait");
		const RE::NiPoint3 h = wait ? wait->HandsAt(0.0f) : RE::NiPoint3{ 0.0f, 36.0f, 62.0f };
		// the hands rest on the edge, just behind its lip
		const RE::NiPoint3 grip = a_edge - a_facing * (0.04f * kUnits) - RE::NiPoint3{ 0.0f, 0.0f, 0.03f * kUnits };
		return grip - Right(a_facing) * h.x - a_facing * h.y - RE::NiPoint3{ 0.0f, 0.0f, h.z };
	}

	bool LedgeRefine(const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing, RE::NiPoint3& a_outEdge, RE::NiPoint3& a_outFacing)
	{
		// the wall face: a horizontal ray just under the top, toward the edge
		const RE::NiPoint3 under = a_edge - RE::NiPoint3{ 0.0f, 0.0f, 0.25f * kUnits };
		RE::NiPoint3       hit, normal;
		if (!CastRay(under - a_facing * (1.0f * kUnits), under + a_facing * (0.5f * kUnits), &hit, &normal)) {
			return false;
		}
		RE::NiPoint3 n{ normal.x, normal.y, 0.0f };
		const float  l = std::sqrt(n.x * n.x + n.y * n.y);
		if (l < 0.7f) {
			return false;  // not a wall (a slope)
		}
		n = n / l;
		a_outFacing = n * -1.0f;
		// the top right above the face
		RE::NiPoint3 top;
		const RE::NiPoint3 p = hit + a_outFacing * (0.15f * kUnits);
		if (!CastRay(p + RE::NiPoint3{ 0.0f, 0.0f, 0.6f * kUnits }, p - RE::NiPoint3{ 0.0f, 0.0f, 0.6f * kUnits }, &top)) {
			return false;
		}
		a_outEdge = { hit.x, hit.y, top.z };
		return true;
	}

	bool LedgeActive() { return g.state != State::kNone; }

	void LedgeBegin(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_edge, const RE::NiPoint3& a_facing)
	{
		g = Ledge{};
		g.edge = a_edge;
		g.facing = a_facing;
		g.state = State::kCatch;
		g.clip = C("hang_catch");
		g.t = 0.0f;
		Hold(a_player, LedgeHangPosition(g.edge, g.facing), true);
		logger::info("ledge: caught at ({:.0f} {:.0f} {:.0f}), room on top: {}", a_edge.x, a_edge.y, a_edge.z, RoomOnTop(g.edge, g.facing));
	}

	void LedgeUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (g.state == State::kNone) {
			return;
		}
		g.t += a_delta;
		ResolveJump(a_player, a_delta);
		SuppressSkyParkour(a_player, a_delta);
		const RE::NiPoint2 in = MoveInput();

		switch (g.state) {
		case State::kCatch:
			{
				const float d = g.clip ? g.clip->duration : 0.1f;
				Hold(a_player, LedgeHangPosition(g.edge, g.facing), true);
				Play(g.clip, g.t / d);
				if (g.t >= d) {
					g.state = State::kHang;
					g.t = 0.0f;
				}
				break;
			}
		case State::kHang:
			{
				const Clip* wait = C("hang_wait");
				Hold(a_player, LedgeHangPosition(g.edge, g.facing), true);
				if (wait) {
					Play(wait, std::fmod(g.t, wait->duration) / wait->duration);
				}
				// AC1 ignores the stick for a moment after the catch; the forward held from running at the wall must be
				// let go before it can pull up (otherwise he climbs straight over)
				if (std::abs(in.x) < 0.3f && std::abs(in.y) < 0.3f) {
					g.neutral = true;
				}
				if (g.t < 0.25f || !g.neutral) {
					break;
				}
				if (in.y > 0.5f && RoomOnTop(g.edge, g.facing)) {
					const bool run = a_player->AsActorState()->IsSprinting() || in.y > 0.95f && RE::PlayerControls::GetSingleton()->data.running;
					g.clip = C(run ? "hang_pullup_run" : "hang_pullup");
					g.from = LedgeHangPosition(g.edge, g.facing);
					g.to = g.edge + g.facing * (0.45f * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, 1.0f };
					g.state = State::kPullUp;
					g.t = 0.0f;
				} else if (in.y < -0.5f) {
					g.clip = C("hang_drop");
					g.from = LedgeHangPosition(g.edge, g.facing);
					g.state = State::kDrop;
					g.t = 0.0f;
				} else if (std::abs(in.x) > 0.5f) {
					const int    dir = in.x > 0.0f ? 1 : -1;
					RE::NiPoint3 next;
					if (CanShimmy(g.edge, g.facing, dir, next)) {
						g.shimmyDir = dir;
						g.edgeFrom = g.edge;
						g.edgeTo = next;
						g.clip = C(std::format("hang_{}_{}", dir > 0 ? "right" : "left", g.openHands ? "open" : "close").c_str());
						g.openHands = !g.openHands;
						g.state = State::kShimmy;
						g.t = 0.0f;
					}
				}
				break;
			}
		case State::kShimmy:
			{
				const float d = g.clip ? g.clip->duration : 0.55f;
				const float u = std::min(1.0f, g.t / d);
				// move along the edge as far as the clip's own sideways motion has gone
				const float total = g.clip ? std::max(0.01f, g.clip->DispAt(1.0f)[0]) : 1.0f;
				const float k = g.clip ? std::clamp(g.clip->DispAt(u)[0] / total, 0.0f, 1.0f) : u;
				g.edge = g.edgeFrom + (g.edgeTo - g.edgeFrom) * k;
				Hold(a_player, LedgeHangPosition(g.edge, g.facing), true);
				Play(g.clip, u);
				if (u >= 1.0f) {
					g.edge = g.edgeTo;
					g.state = State::kHang;
					g.t = 0.3f;  // straight on to the next step if the key is still held
				}
				break;
			}
		case State::kPullUp:
			{
				const float d = g.clip ? g.clip->duration : 1.0f;
				const float u = std::min(1.0f, g.t / d);
				// AC1 root motion (into the wall, up) plus the linear correction onto the standing spot
				const auto   disp = g.clip ? g.clip->DispAt(u) : std::array<float, 2>{ 0.0f, 0.0f };
				const auto   end = g.clip ? g.clip->DispAt(1.0f) : std::array<float, 2>{ 0.0f, 0.0f };
				const RE::NiPoint3 anim = g.from + g.facing * (disp[0] * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, disp[1] * kUnits };
				const RE::NiPoint3 animEnd = g.from + g.facing * (end[0] * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, end[1] * kUnits };
				RE::NiPoint3       p = anim + (g.to - animEnd) * u;
				p.z = std::max(p.z, g.from.z);
				Hold(a_player, p, true);
				// fade back to the game's own animation over the last 0.15 s (he is standing / running by then)
				Play(g.clip, u, std::min(1.0f, (d - g.t) / 0.15f));
				if (u >= 1.0f) {
					Hold(a_player, g.to, true);
					Gravity(a_player, true);
					ClearPose();
					g.state = State::kNone;
					logger::info("ledge: pulled up");
				}
				break;
			}
		case State::kDrop:
			{
				// AC1's let-go, then Skyrim's fall takes over (it pushes off the wall a little)
				const float d = 0.3f;
				const float u = std::min(1.0f, g.t / d);
				Hold(a_player, g.from - g.facing * (0.3f * kUnits * u), true);
				Play(g.clip, g.clip ? (g.t / g.clip->duration) : 0.0f, 1.0f - u);
				if (u >= 1.0f) {
					Hold(a_player, g.from - g.facing * (0.3f * kUnits), false);
					Gravity(a_player, true);
					ClearPose();
					g.state = State::kNone;
					logger::info("ledge: let go");
				}
				break;
			}
		default:
			break;
		}
	}
}
