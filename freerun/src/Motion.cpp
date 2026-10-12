#include "Motion.h"
#include "PosePlayer.h"
#include "TargetJump.h"

namespace Freerun
{
	namespace
	{
		float g_savedGravity = -1.0f;
	}

	void HoldAt(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_at, float a_yaw, bool a_onGround, bool a_floating)
	{
		if (a_player->GetPosition().GetDistance(a_at) > 0.5f) {
			a_player->SetPosition(a_at, true);
		}
		const float dy = std::fmod(a_player->data.angle.z - a_yaw + 3.0f * RE::NI_PI, 2.0f * RE::NI_PI) - RE::NI_PI;
		if (std::abs(dy) > 0.01f) {
			a_player->data.angle.z = a_yaw;
		}
		auto* controller = a_player->GetCharController();
		if (!controller) {
			return;
		}
		if (a_floating && g_savedGravity < 0.0f) {
			g_savedGravity = controller->gravity;
			controller->gravity = 0.0f;
		}
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

	void RestoreGravity(RE::PlayerCharacter* a_player)
	{
		auto* controller = a_player->GetCharController();
		if (controller && g_savedGravity >= 0.0f) {
			controller->gravity = g_savedGravity;
		}
		g_savedGravity = -1.0f;
	}

	void ResolveJumpState(RE::PlayerCharacter* a_player, float a_delta, float& a_clock)
	{
		bool inJump = false;
		a_player->GetGraphVariableBool("bInJumpState", inJump);
		if (!inJump) {
			a_clock = 0.0f;
			return;
		}
		const float before = a_clock;
		a_clock += a_delta;
		if (before < 0.2f && a_clock >= 0.2f) {
			a_player->NotifyAnimationGraph("JumpLand");
		} else if (before < 0.6f && a_clock >= 0.6f) {
			a_player->NotifyAnimationGraph("JumpLandEnd");
		} else if (before < 1.0f && a_clock >= 1.0f) {
			a_player->NotifyAnimationGraph("JumpLandFailSafe");
		}
	}

	void SetControlsLocked(bool a_locked)
	{
		static bool locked = false;
		if (locked == a_locked) {
			return;
		}
		if (auto* map = RE::ControlMap::GetSingleton()) {
			map->ToggleControls(RE::UserEvents::USER_EVENT_FLAG::kMovement, !a_locked, false);
			map->ToggleControls(RE::UserEvents::USER_EVENT_FLAG::kJumping, !a_locked, false);
			locked = a_locked;
		}
	}

	float ActorScale(RE::PlayerCharacter* a_player)
	{
		auto* root = a_player->Get3D(false);
		const float s = root ? root->world.scale : a_player->GetScale();
		return s > 0.1f ? s : 1.0f;
	}

	void PlaySoundAtPlayer(RE::PlayerCharacter* a_player, const char* a_editorID)
	{
		auto* audio = RE::BSAudioManager::GetSingleton();
		if (!audio) {
			return;
		}
		RE::BSSoundHandle handle;
		audio->GetSoundHandleByName(handle, a_editorID, 0x1A);
		if (handle.IsValid()) {
			handle.SetPosition(a_player->GetPosition());
			if (auto* root = a_player->Get3D(false)) {
				handle.SetObjectToFollow(root);
			}
			handle.Play();
		}
	}

	float YawOf(const RE::NiPoint3& a_dir) { return std::atan2(a_dir.x, a_dir.y); }
	RE::NiPoint3 DirOf(float a_yaw) { return { std::sin(a_yaw), std::cos(a_yaw), 0.0f }; }
	RE::NiPoint3 RightOf(const RE::NiPoint3& a_dir) { return { a_dir.y, -a_dir.x, 0.0f }; }

	RE::NiPoint3 InputWorld()
	{
		const RE::NiPoint2 m = RawMove();
		float              yaw = 0.0f;
		auto*              camera = RE::PlayerCamera::GetSingleton();
		if (camera && camera->cameraRoot) {
			const auto& r = camera->cameraRoot->world.rotate;
			yaw = std::atan2(r.entry[0][1], r.entry[1][1]);  // the camera's forward (its local +Y) on the ground
		} else if (auto* player = RE::PlayerCharacter::GetSingleton()) {
			yaw = player->data.angle.z;
		}
		const RE::NiPoint3 f = DirOf(yaw);
		return f * m.y + RightOf(f) * m.x;
	}

	void PlayClip(const char* a_name, float a_u, float a_weight)
	{
		if (const Clip* c = FindClip(a_name)) {
			Blend b;
			b.parts.emplace_back(c, 1.0f);
			SetPose(b, a_u, a_weight);
		}
	}

	float ClipDuration(const char* a_name, float a_fallback)
	{
		const Clip* c = FindClip(a_name);
		return c ? c->duration : a_fallback;
	}
}
