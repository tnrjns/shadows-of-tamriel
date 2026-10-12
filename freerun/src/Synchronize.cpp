#include "Synchronize.h"
#include "Motion.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		constexpr float kIn = 0.5f;      // into the crouch
		constexpr float kSweep = 4.5f;   // the camera's turn round him
		constexpr float kOut = 0.5f;     // back up

		enum class State
		{
			kNone,
			kIn,
			kSweep,
			kOut,
		};

		struct Sync
		{
			State        state{ State::kNone };
			float        t{ 0.0f };
			float        loopT{ 0.0f };
			float        w{ 0.0f };
			float        turned{ 0.0f };  // camera yaw added so far
			float        yaw{ 0.0f };
			RE::NiPoint3 at;
			bool         sounded{ false };
		};
		Sync g;

		RE::ThirdPersonState* Third()
		{
			auto* camera = RE::PlayerCamera::GetSingleton();
			if (camera && camera->currentState && camera->currentState->id == RE::CameraState::kThirdPerson) {
				return static_cast<RE::ThirdPersonState*>(camera->currentState.get());
			}
			return nullptr;
		}

		void PlaySyncSound()
		{
			static RE::BGSSoundDescriptorForm* sound = nullptr;
			static bool                         looked = false;
			if (!looked) {
				looked = true;
				if (auto* dh = RE::TESDataHandler::GetSingleton()) {
					sound = dh->LookupForm<RE::BGSSoundDescriptorForm>(0x850, "AltairLeapOfFaith.esp");
				}
				if (!sound) {
					logger::warn("sync: AltairSynchronizeSD not found (is AltairLeapOfFaith.esp up to date?)");
				}
			}
			auto* audio = RE::BSAudioManager::GetSingleton();
			if (!sound || !audio) {
				return;
			}
			RE::BSSoundHandle handle;
			if (audio->GetSoundHandle(handle, sound, 0x1A) && handle.IsValid()) {
				handle.Play();
			}
		}

		bool Moving()
		{
			const auto m = RawMove();
			return std::abs(m.x) > 0.4f || std::abs(m.y) > 0.4f;
		}
	}

	bool SyncActive() { return g.state != State::kNone; }

	bool SyncTry(RE::PlayerCharacter* a_player)
	{
		if (g.state != State::kNone || !LeapArmed(a_player) || !FindClip("sync_wait")) {
			return false;
		}
		auto* controller = a_player->GetCharController();
		if (!controller || controller->context.currentState != RE::hkpCharacterStateType::kOnGround) {
			return false;
		}
		g = Sync{};
		g.state = State::kIn;
		g.at = a_player->GetPosition();
		g.yaw = a_player->data.angle.z;
		logger::info("sync: synchronizing at ({:.0f} {:.0f} {:.0f})", g.at.x, g.at.y, g.at.z);
		return true;
	}

	void SyncUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		if (g.state == State::kNone) {
			return;
		}
		g.t += a_delta;
		g.loopT += a_delta;
		HoldAt(a_player, g.at, g.yaw, true, false);

		switch (g.state) {
		case State::kIn:
			g.w = std::min(1.0f, g.t / kIn);
			if (!g.sounded && g.t > 0.2f) {
				g.sounded = true;
				PlaySyncSound();
			}
			if (g.t >= kIn) {
				g.state = State::kSweep;
				g.t = 0.0f;
			}
			break;
		case State::kSweep:
			{
				// one turn of the camera round him, easing in and out (AC1's synchronization swoop)
				const float u = std::min(1.0f, g.t / kSweep);
				const float e = u * u * u * (u * (u * 6.0f - 15.0f) + 10.0f);
				const float want = 2.0f * RE::NI_PI * e;
				if (auto* third = Third()) {
					third->freeRotationEnabled = true;
					third->freeRotation.x += want - g.turned;
				}
				g.turned = want;
				if (u >= 1.0f || (g.t > 1.0f && Moving())) {
					if (u >= 1.0f) {
						RE::SendHUDMessage::ShowHUDMessage("Viewpoint synchronized");
					}
					g.state = State::kOut;
					g.t = 0.0f;
				}
				break;
			}
		case State::kOut:
			g.w = std::max(0.0f, 1.0f - g.t / kOut);
			if (g.t >= kOut) {
				ClearPose();
				g.state = State::kNone;
				logger::info("sync: done");
				return;
			}
			break;
		default:
			break;
		}
		if (const Clip* c = FindClip("sync_wait")) {
			Blend b;
			b.parts.emplace_back(c, 1.0f);
			const float x = g.w;
			SetPose(b, std::fmod(g.loopT, c->duration) / c->duration, x * x * (3.0f - 2.0f * x));
		}
	}
}
