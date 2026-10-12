// AltairFreerun: AC1-style free-running for Skyrim. See docs/AC1_FREERUN_PLAN.md.
// P0: finds AC1 jump targets around the player and draws them. P1: sprint-jumps lock onto the chosen target.

#include "EdgeFinder.h"
#include "TargetJump.h"
#include "PosePlayer.h"
#include "Ledge.h"
#include "Pray.h"
#include "Narrow.h"
#include "Swing.h"
#include "Walling.h"
#include "HayHide.h"
#include "SKSEMenuFramework.h"

namespace
{
	float g_probeTimer = 0.0f;

	struct PlayerUpdateHook
	{
		static void thunk(RE::PlayerCharacter* a_this, float a_delta)
		{
			func(a_this, a_delta);
			if (a_this != RE::PlayerCharacter::GetSingleton() || a_delta <= 0.0f) {
				return;
			}
			Freerun::HayUpdate(a_this, a_delta);
			Freerun::PrayUpdate(a_this, a_delta);
			Freerun::LedgeUpdate(a_this, a_delta);
			Freerun::WallRunUpdate(a_this, a_delta);
			Freerun::NarrowUpdate(a_this, a_delta);
			Freerun::SwingUpdate(a_this, a_delta);
			Freerun::TargetJumpUpdate(a_this, a_delta);
			g_probeTimer -= a_delta;
			const auto& cfg = Freerun::GetSettings();
			if ((cfg.overlay || cfg.targetJumps) && !Freerun::TargetJumpActive() && !Freerun::LedgeActive() &&
				!Freerun::NarrowActive() && !Freerun::SwingActive() && !Freerun::WallRunActive() && !Freerun::HayActive() &&
				g_probeTimer <= 0.0f) {
				g_probeTimer = 0.1f;  // 10 probes a second is plenty for a preview
				Freerun::Update(a_this);
			}
		}
		static inline REL::Relocation<decltype(thunk)> func;
	};

	// after Skyrim's animation update: AC1 clips overwrite the pose while a free-run jump plays
	struct PlayerAnimationHook
	{
		static void thunk(RE::PlayerCharacter* a_this, float a_delta)
		{
			func(a_this, a_delta);
			if (a_this == RE::PlayerCharacter::GetSingleton()) {
				Freerun::ApplyPose(a_this, a_delta);
			}
		}
		static inline REL::Relocation<decltype(thunk)> func;
	};

	// the jump key, seen before the game (and other mods) act on it
	class InputSink : public RE::BSTEventSink<RE::InputEvent*>
	{
	public:
		RE::BSEventNotifyControl ProcessEvent(RE::InputEvent* const* a_events, RE::BSTEventSource<RE::InputEvent*>*) override
		{
			auto* ue = RE::UserEvents::GetSingleton();
			for (auto* e = a_events ? *a_events : nullptr; e; e = e->next) {
				if (auto* b = e->AsButtonEvent(); b && ue) {
					const auto& id = b->QUserEvent();
					if (id == ue->jump && b->IsDown()) {
						Freerun::NotifyJumpPressed();
					}
					if (b->GetDevice() == RE::INPUT_DEVICE::kKeyboard && b->IsDown() &&
						static_cast<int>(b->GetIDCode()) == Freerun::GetSettings().prayKey && !RE::UI::GetSingleton()->GameIsPaused()) {
						Freerun::PrayKeyPressed();
					}
					const float v = b->IsPressed() ? 1.0f : 0.0f;
					if (id == ue->forward) {
						Freerun::SetRawMove(0, v);
					} else if (id == ue->back) {
						Freerun::SetRawMove(1, v);
					} else if (id == ue->strafeLeft) {
						Freerun::SetRawMove(2, v);
					} else if (id == ue->strafeRight) {
						Freerun::SetRawMove(3, v);
					} else if (id == ue->sprint) {
						Freerun::SetRawSprint(v > 0.0f);
					}
				} else if (auto* t = e->AsThumbstickEvent(); t && t->IsLeft()) {
					Freerun::SetRawMove(4, t->xValue);
					Freerun::SetRawMove(5, t->yValue);
				}
			}
			return RE::BSEventNotifyControl::kContinue;
		}
		static InputSink* Get()
		{
			static InputSink s;
			return &s;
		}
	};

	ImGuiMCP::ImU32 Colour(const Freerun::Candidate& a_c, bool a_chosen)
	{
		if (a_chosen) {
			return IM_COL32(255, 255, 255, 255);
		}
		if (!a_c.inReach) {
			return IM_COL32(120, 120, 120, 160);
		}
		switch (a_c.type) {
		case Freerun::EdgeType::kRoof:
			return IM_COL32(60, 220, 90, 230);
		case Freerun::EdgeType::kHang:
			return IM_COL32(240, 200, 40, 230);
		default:
			return IM_COL32(60, 200, 240, 230);
		}
	}

	void __stdcall DrawOverlay()
	{
		if (!Freerun::GetSettings().overlay) {
			return;
		}
		auto* camera = RE::Main::WorldRootCamera();
		if (!camera) {
			return;
		}
		const auto  snap = Freerun::Latest();
		auto*       list = ImGuiMCP::GetForegroundDrawList();
		const auto* vp = ImGuiMCP::GetMainViewport();
		if (!list || !vp) {
			return;
		}
		for (int i = 0; i < static_cast<int>(snap.candidates.size()); ++i) {
			const auto& c = snap.candidates[i];
			float       x = 0.0f, y = 0.0f, z = 0.0f;
			if (!RE::NiCamera::WorldPtToScreenPt3(camera->GetRuntimeData().worldToCam, camera->GetRuntimeData2().port,
					c.point, x, y, z, 1e-5f) ||
				z < 0.0f) {
				continue;
			}
			const ImGuiMCP::ImVec2 p{ vp->Pos.x + x * vp->Size.x, vp->Pos.y + (1.0f - y) * vp->Size.y };
			const bool             chosen = i == snap.chosen;
			ImGuiMCP::ImDrawListManager::AddCircleFilled(list, p, chosen ? 9.0f : 6.0f, Colour(c, chosen), 16);
			if (chosen) {
				ImGuiMCP::ImDrawListManager::AddCircle(list, p, 15.0f, IM_COL32(255, 255, 255, 255), 24, 2.0f);
			}
		}
	}

	void __stdcall RenderPage()
	{
		auto& cfg = Freerun::GetSettings();
		bool  changed = false;
		ImGuiMCP::SeparatorText("Jumps");
		changed |= ImGuiMCP::Checkbox("Target-locked jumps", &cfg.targetJumps);
		ImGuiMCP::TextWrapped("Sprint and jump at a gap: Altair lands exactly on the chosen roof edge or beam, as in AC1.");
		changed |= ImGuiMCP::Checkbox("Only while sprinting (AC1 high profile)", &cfg.requireSprint);
		changed |= ImGuiMCP::Checkbox("AC1 jump animations", &cfg.ac1Animations);
		changed |= ImGuiMCP::Checkbox("Free-run: jump gaps by himself while sprinting", &cfg.autoJump);
		ImGuiMCP::TextWrapped("As in AC1: sprint at the edge of a roof and he jumps to the next target on his own, or up onto a step "
			"he can't run up. No timing needed.");
		ImGuiMCP::TextWrapped("AC1's own takeoff, flight and landing, chosen and blended by distance and height as in AC1.");
		changed |= ImGuiMCP::SliderFloat("Arc height", &cfg.arcHeight, 0.3f, 2.5f, "%.2f", 0x10);
		changed |= ImGuiMCP::Checkbox("Catch ledges (hang, shimmy, pull up)", &cfg.ledges);
		ImGuiMCP::TextWrapped("Jump at a ledge too high to land on and he catches it. Hanging: A / D shimmy, W pulls up (hold sprint to "
			"run straight off), S lets go.");
		changed |= ImGuiMCP::Checkbox("Beams, poles, swing bars, wall run", &cfg.p4);
		ImGuiMCP::TextWrapped("Beams: crouched balance walk (W along, S turns round, sprint jogs; sprint off the end jumps on). Poles: "
			"perch, push a direction and jump. Bars: jump at a bar above your head to swing; jump (or hold sprint) lets go forward, "
			"S drops. Wall run: jump at a wall too tall to catch and he runs up it to the ledge.");
		changed |= ImGuiMCP::Checkbox("Hide in haystacks after a leap of faith", &cfg.hayHide);
		ImGuiMCP::TextWrapped("Land a leap of faith in a haystack and he sinks in and hides; move or jump to hop out.");
		ImGuiMCP::SeparatorText("Movement");
		changed |= ImGuiMCP::SliderFloat("Walk / run / sprint smoothing (s)", &cfg.gaitSmoothing, 0.0f, 0.8f, "%.2f", 0x10);
		ImGuiMCP::TextWrapped("Eases the body from one gait into the next when you start or stop sprinting. 0 = off.");
		ImGuiMCP::SeparatorText("Prayer");
		changed |= ImGuiMCP::Checkbox("AC1 prayer on B", &cfg.pray);
		ImGuiMCP::TextWrapped("Press B to bow your head and pray like Altair blending in with the scholars; B again or move to stop.");
		changed |= ImGuiMCP::Checkbox("Close the eyes while praying", &cfg.prayCloseEyes);
		ImGuiMCP::SeparatorText("Preview");
		changed |= ImGuiMCP::Checkbox("Show jump targets", &cfg.overlay);
		ImGuiMCP::TextWrapped(
			"Green: roof edge he can land on. Yellow: ledge to catch and hang from (coming in a later update). Blue: beam. "
			"Grey: out of AC1's reach for your current speed. White ring: the target AC1's rules pick.");
		ImGuiMCP::SeparatorText("Reset");
		if (ImGuiMCP::Button("Reset all free-run settings to defaults")) {
			cfg = Freerun::Settings{};
			changed = true;
		}
		if (changed) {
			cfg.Save();
		}
	}

	void OnMessage(SKSE::MessagingInterface::Message* a_msg)
	{
		if (a_msg->type == SKSE::MessagingInterface::kDataLoaded) {
			Freerun::GetSettings().Load();
			REL::Relocation<std::uintptr_t> playerVtbl{ RE::VTABLE_PlayerCharacter[0] };
			PlayerUpdateHook::func = playerVtbl.write_vfunc(0xAD, PlayerUpdateHook::thunk);
			PlayerAnimationHook::func = playerVtbl.write_vfunc(0x7D, PlayerAnimationHook::thunk);
			if (auto* input = RE::BSInputDeviceManager::GetSingleton()) {
				input->AddEventSink(InputSink::Get());
			}
			if (SKSEMenuFramework::IsInstalled()) {
				SKSEMenuFramework::SetSection("Altair AC1");
				SKSEMenuFramework::AddSectionItem("Free-run (preview)", RenderPage);
				SKSEMenuFramework::AddHudElement(DrawOverlay);
			}
			logger::info("AltairFreerun P2 ready");
		}
	}
}

SKSEPluginLoad(const SKSE::LoadInterface* a_skse)
{
	SKSE::Init(a_skse);
	if (auto dir = SKSE::log::log_directory()) {
		auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>((*dir / "AltairFreerun.log").string(), true);
		auto log = std::make_shared<spdlog::logger>("log", std::move(sink));
		log->set_level(spdlog::level::info);
		log->flush_on(spdlog::level::info);
		spdlog::set_default_logger(std::move(log));
	}
	SKSE::GetMessagingInterface()->RegisterListener(OnMessage);
	return true;
}
