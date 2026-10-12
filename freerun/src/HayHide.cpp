#include "HayHide.h"
#include "Motion.h"
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
			kEnter,
			kHidden,
			kOut,
		};

		struct Hay
		{
			State        state{ State::kNone };
			RE::NiPoint3 from, inside, exit, dir;
			float        yaw{ 0.0f };
			float        t{ 0.0f }, loopT{ 0.0f };
			float        radius{ 1.3f * U };
			float        jumpClock{ 0.0f };
			bool         neutral{ false };
		};
		Hay   g;
		float g_seek = 0.0f;
		float g_divingFor = 0.0f;  // seconds since the leap-of-faith dive was last seen armed

		// the AltairHaystack activator's runtime form id (looked up untyped: the typed lookup's cast rejected it)
		RE::FormID HayBase()
		{
			static RE::FormID id = 0;
			static bool       looked = false;
			if (!looked) {
				if (auto* dh = RE::TESDataHandler::GetSingleton()) {
					if (auto* form = dh->LookupForm(0x816, "AltairLeapOfFaith.esp")) {
						id = form->GetFormID();
					}
					looked = true;
				}
			}
			return id;
		}

		bool DiveArmed(RE::PlayerCharacter* a_player)
		{
			static RE::SpellItem* dive = nullptr;
			static bool           looked = false;
			if (!looked) {
				looked = true;
				if (auto* dh = RE::TESDataHandler::GetSingleton()) {
					dive = dh->LookupForm<RE::SpellItem>(0x801, "AltairLeapOfFaith.esp");
				}
			}
			return dive && a_player->HasSpell(dive);
		}

		// the nearest haystack whose top the player is coming down into
		RE::TESObjectREFR* HayBelow(RE::PlayerCharacter* a_player, float& a_radius)
		{
			const RE::FormID base = HayBase();
			auto*            tes = RE::TES::GetSingleton();
			if (!base || !tes) {
				return nullptr;
			}
			const RE::NiPoint3 p = a_player->GetPosition();
			RE::TESObjectREFR* best = nullptr;
			float              bestD = 1e9f;
			tes->ForEachReferenceInRange(a_player, 1200.0f, [&](RE::TESObjectREFR* a_ref) {
				const auto* b = a_ref ? a_ref->GetBaseObject() : nullptr;
				if (b && b->GetFormID() == base && !a_ref->IsDisabled()) {
					const RE::NiPoint3 h = a_ref->GetPosition();
					const float        d = std::sqrt((p.x - h.x) * (p.x - h.x) + (p.y - h.y) * (p.y - h.y));
					if (d < bestD) {
						bestD = d;
						best = a_ref;
					}
				}
				return RE::BSContainer::ForEachResult::kContinue;
			});
			if (!best) {
				static float logT = 0.0f;
				const float  now = static_cast<float>(GetTickCount64()) / 1000.0f;
				if (now - logT > 1.0f) {
					logT = now;
					logger::info("hay: falling / armed, but no haystack within 17 m");
				}
				return nullptr;
			}
			const float scale = best->GetScale();
			a_radius = 2.4f * U * scale;  // the AC1 haystack is ~5 x 4.3 m
			const float above = p.z - best->GetPositionZ();
			const bool  in = bestD < a_radius && above < 2.6f * U * scale && above > -0.6f * U;
			static float logT = 0.0f;
			if (!in && bestD < 6.0f * U) {
				const float now = static_cast<float>(GetTickCount64()) / 1000.0f;
				if (now - logT > 0.5f) {
					logT = now;
					logger::info("hay: armed, nearest haystack {:.1f} m away, {:.1f} m below (needs < {:.1f} m)", bestD / U, above / U, a_radius / U);
				}
			}
			return in ? best : nullptr;
		}
	}

	bool HayActive() { return g.state != State::kNone; }

	void HayUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (g.state == State::kNone) {
			// watch for a leap of faith (the dive ability) or any fall of 3 m+ coming down into a haystack (as in AC1)
			auto*      controller = a_player->GetCharController();
			const bool falling = controller && controller->context.currentState == RE::hkpCharacterStateType::kInAir &&
			                     controller->fallStartHeight - a_player->GetPositionZ() > 3.0f * U;
			const bool armed = DiveArmed(a_player);
			if (armed || falling) {
				g_divingFor = 0.0f;
			} else {
				g_divingFor += a_delta;
			}
			static bool loggedArmed = false;
			if (armed && !loggedArmed) {
				logger::info("hay: leap armed (haystack form {})", HayBase() ? "found" : "NOT FOUND - is AltairLeapOfFaith.esp loaded?");
			}
			loggedArmed = armed;
			if (g_divingFor > 1.5f || !GetSettings().hayHide) {
				return;
			}
			// falling in or just landed inside (the haystack has no collision): either way he goes into it
			g_seek -= a_delta;
			if (g_seek > 0.0f || TargetJumpActive()) {
				return;
			}
			g_seek = 0.05f;
			float r = 0.0f;
			auto* hay = HayBelow(a_player, r);
			if (!hay) {
				return;
			}
			g = Hay{};
			g.radius = r;
			g.from = a_player->GetPosition();
			g.inside = hay->GetPosition() + RE::NiPoint3{ 0.0f, 0.0f, 2.0f };
			RE::NiPoint3 d = g.inside - g.from;
			d.z = 0.0f;
			const float l = std::sqrt(d.x * d.x + d.y * d.y);
			g.dir = l > 5.0f ? d / l : DirOf(a_player->data.angle.z);
			g.yaw = YawOf(g.dir);
			g.state = State::kEnter;
			logger::info("hay: diving in");
			return;
		}

		g.t += a_delta;
		ResolveJumpState(a_player, a_delta, g.jumpClock);
		switch (g.state) {
		case State::kEnter:
			{
				// AC1's air-to-haystack, sinking down into the hay
				const float d = ClipDuration("hay_enter", 0.73f);
				const float u = std::min(1.0f, g.t / d);
				const float e = u * u * (3.0f - 2.0f * u);
				HoldAt(a_player, g.from + (g.inside - g.from) * e, g.yaw, true, true);
				PlayClip("hay_enter", u);
				if (u >= 1.0f) {
					g.state = State::kHidden;
					g.t = 0.0f;
					g.loopT = 0.0f;
					logger::info("hay: hidden");
				}
				break;
			}
		case State::kHidden:
			{
				g.loopT += a_delta;
				const float d = ClipDuration("hay_wait", 5.0f);
				PlayClip("hay_wait", std::fmod(g.loopT, d) / d);
				HoldAt(a_player, g.inside, g.yaw, true, true);
				const RE::NiPoint3 in = InputWorld();
				const float        push = std::sqrt(in.x * in.x + in.y * in.y);
				if (push < 0.3f) {
					g.neutral = true;  // a key held from the leap doesn't hop him straight out
				}
				const bool jump = TakeJumpPress();
				if (g.t > 0.6f && g.neutral && (push > 0.5f || jump)) {
					g.dir = push > 0.5f ? in / push : g.dir;
					g.exit = g.inside + g.dir * (g.radius + 0.45f * U);
					g.from = g.inside;
					g.state = State::kOut;
					g.t = 0.0f;
				}
				break;
			}
		case State::kOut:
			{
				// AC1's hop out, turning to the way out and stepping clear of the hay
				const float d = ClipDuration("hay_out", 1.2f);
				const float u = std::min(1.0f, g.t / d);
				const float turn = std::min(1.0f, g.t / 0.25f);
				float       dy = std::fmod(YawOf(g.dir) - g.yaw + 3.0f * RE::NI_PI, 2.0f * RE::NI_PI) - RE::NI_PI;
				const float yaw = g.yaw + dy * turn;
				const float move = std::clamp((u - 0.15f) / 0.55f, 0.0f, 1.0f);  // the hop: early-middle of the clip
				const float e = move * move * (3.0f - 2.0f * move);
				HoldAt(a_player, g.from + (g.exit - g.from) * e, yaw, true, true);
				PlayClip("hay_out", u, std::min(1.0f, (d - g.t) / 0.2f));
				if (u >= 1.0f) {
					RestoreGravity(a_player);
					ClearPose();
					g.state = State::kNone;
					g_divingFor = 10.0f;
					logger::info("hay: out");
				}
				break;
			}
		default:
			break;
		}
	}
}
