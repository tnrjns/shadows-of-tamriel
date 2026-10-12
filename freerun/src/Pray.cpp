#include "Pray.h"
#include "Ledge.h"
#include "PosePlayer.h"
#include "TargetJump.h"
#include "HayHide.h"

namespace Freerun
{
	namespace
	{
		constexpr float kEase = 0.45f;  // seconds into / out of the prayer

		enum class State
		{
			kNone,
			kIn,
			kLoop,
			kOut,
		};
		State             g_state = State::kNone;
		float             g_t = 0.0f;      // time in the prayer loop
		float             g_w = 0.0f;      // pose weight
		std::atomic<bool> g_pressed{ false };
		bool              g_eyesClosed = false;

		// Close / open both eyes with the face's blink modifiers (0 BlinkLeft, 1 BlinkRight), the values the "mfg
		// modifier" console command sets; the automatic blinking is held off while they are shut.
		void SetEyes(RE::PlayerCharacter* a_player, float a_closed)
		{
			auto* face = a_player->GetFaceGenAnimationData();
			if (!face) {
				return;
			}
			RE::BSSpinLockGuard guard(face->lock);
			face->modifierKeyFrame.SetValue(0, a_closed);
			face->modifierKeyFrame.SetValue(1, a_closed);
			if (a_closed > 0.0f) {
				face->eyesBlinkingStage = RE::BSFaceGenAnimationData::EyesBlinkingStage::BlinkDelay;
				face->eyesBlinkingTimer = 5.0f;
			}
		}

		bool Moving()
		{
			const auto m = RawMove();
			return std::abs(m.x) > 0.4f || std::abs(m.y) > 0.4f;
		}
	}

	void PrayKeyPressed() { g_pressed = true; }

	bool PrayActive() { return g_state != State::kNone; }

	void PrayUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		const bool pressed = g_pressed.exchange(false);
		if (!GetSettings().pray) {
			if (g_state != State::kNone) {
				g_state = State::kOut;
			} else {
				return;
			}
		}

		switch (g_state) {
		case State::kNone:
			{
				if (!pressed || TargetJumpActive() || LedgeActive() || HayActive()) {
					break;
				}
				bool inJump = false;
				a_player->GetGraphVariableBool("bInJumpState", inJump);
				auto* controller = a_player->GetCharController();
				if (inJump || (controller && controller->context.currentState != RE::hkpCharacterStateType::kOnGround)) {
					break;
				}
				g_state = State::kIn;
				g_t = 0.0f;
				g_w = 0.0f;
				logger::info("prayer");
				break;
			}
		case State::kIn:
		case State::kLoop:
			if (pressed || Moving() || TargetJumpActive() || LedgeActive()) {
				g_state = State::kOut;
				break;
			}
			g_w = std::min(1.0f, g_w + a_delta / kEase);
			if (g_w >= 1.0f) {
				g_state = State::kLoop;
			}
			break;
		case State::kOut:
			g_w = std::max(0.0f, g_w - a_delta / kEase);
			if (g_w <= 0.0f) {
				g_state = State::kNone;
			}
			break;
		}

		static bool posing = false;
		if (g_state == State::kNone) {
			if (g_eyesClosed) {
				SetEyes(a_player, 0.0f);
				g_eyesClosed = false;
			}
			if (posing) {
				ClearPose();
				posing = false;
			}
			return;
		}
		posing = true;
		g_t += a_delta;
		if (const Clip* c = FindClip("pray_blend")) {
			Blend b;
			b.parts.emplace_back(c, 1.0f);
			const float x = g_w;  // smoothstep the ease
			SetPose(b, std::fmod(g_t, c->duration) / c->duration, x * x * (3.0f - 2.0f * x));
		}
		if (GetSettings().prayCloseEyes) {
			SetEyes(a_player, std::clamp(g_w * 1.4f - 0.2f, 0.0f, 1.0f));  // the eyes shut as the head bows
			g_eyesClosed = true;
		}
	}
}
