#include "TargetJump.h"
#include "PosePlayer.h"
#include "Ledge.h"
#include "Motion.h"
#include "Narrow.h"
#include "Swing.h"
#include "Walling.h"
#include "HayHide.h"

namespace Freerun
{
	namespace
	{
		constexpr float kUnits = 70.0f;
		constexpr auto  kIni = "Data/SKSE/Plugins/AltairFreerun.ini";
		constexpr float kBlendIn = 0.06f;   // game pose -> AC1 takeoff
		constexpr float kBlendOut = 0.15f;  // AC1 reception -> game pose (back to the run)

		Settings g_settings;

		enum class Phase
		{
			kNone,
			kTakeoff,
			kFlight,
			kReception,
		};

		struct Jump
		{
			Phase        phase{ Phase::kNone };
			RE::NiPoint3 from;
			RE::NiPoint3 to;
			RE::NiPoint3 dir;       // horizontal jump direction
			float        yaw{ 0.0f };
			Blend        takeoff, flight, reception;
			float        t1{ 0.0f }, t2{ 0.0f }, tr{ 0.0f };  // takeoff, flight, reception durations
			float        flightStretch{ 1.0f };
			std::array<float, 2> dispEnd{ 0.0f, 0.0f };     // AC1 displacement at the end of the flight (m)
			float        apex{ 0.0f };                     // P1 arc (no AC1 clips)
			float        t{ 0.0f };
			bool         animated{ false };
			bool         manual{ false };   // started from Skyrim's own jump (its behavior graph is in the jump state)
			float        settle{ 0.0f };    // time since the hand-back, while waiting for Skyrim to register the landing
			bool         settling{ false };
			bool         hang{ false };     // a ledge catch: ends in a hang
			RE::NiPoint3 hangEdge, hangFacing;
			EdgeType     type{ EdgeType::kRoof };
			RE::NiPoint3 barFacing;         // swing bar catch
		};
		Jump  g_jump;
		std::atomic<bool> g_jumpPressed{ false };
		bool  g_wasInJump = false;
		float g_cooldown = 0.0f;
		bool g_packLoaded = false;

		bool LeapOfFaithArmed(RE::PlayerCharacter* a_player)
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

		RE::NiPoint3 LandingPoint(const Candidate& a_c, const RE::NiPoint3& a_from)
		{
			RE::NiPoint3 dir = a_c.point - a_from;
			dir.z = 0.0f;
			const float l = std::sqrt(dir.x * dir.x + dir.y * dir.y);
			if (l > 1.0f) {
				dir = dir / l;
			}
			const float inset = a_c.type == EdgeType::kBeam ? 0.25f : 0.35f;
			return a_c.point + dir * (inset * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, 2.0f };
		}

		const Candidate* LandingTarget(const Snapshot& a_snap)
		{
			const Candidate* best = nullptr;
			for (const auto& c : a_snap.candidates) {
				if (!c.inReach || (c.type == EdgeType::kHang && !g_settings.ledges) ||
					((c.type == EdgeType::kBar || c.type == EdgeType::kPole) && !g_settings.p4)) {
					continue;
				}
				if (!best || c.score > best->score) {
					best = &c;
				}
			}
			return best;
		}

		// AC1's jump items by direction class and distance: front 0.5/3/5.5 m, up 0.5/3 m, down 0.5/5.5 m, blended
		// between the two nearest distances (Human__ComputeJumpAnimBlend 0xB1EC40, simplified to one axis).
		Blend Pick(const char* a_kind, const char* a_family, const std::vector<int>& a_buckets, float a_d)
		{
			Blend b;
			std::vector<std::pair<const Clip*, float>> have;
			for (int cm : a_buckets) {
				if (const Clip* c = FindClip(std::format("{}_{}_{:03}", a_kind, a_family, cm))) {
					have.emplace_back(c, cm / 100.0f);
				}
			}
			if (have.empty()) {
				return b;
			}
			if (a_d <= have.front().second || have.size() == 1) {
				b.parts.emplace_back(have.front().first, 1.0f);
				return b;
			}
			for (std::size_t i = 0; i + 1 < have.size(); ++i) {
				if (a_d <= have[i + 1].second) {
					const float u = (a_d - have[i].second) / (have[i + 1].second - have[i].second);
					b.parts.emplace_back(have[i].first, 1.0f - u);
					b.parts.emplace_back(have[i + 1].first, u);
					return b;
				}
			}
			b.parts.emplace_back(have.back().first, 1.0f);
			return b;
		}

		Blend Nearest(const char* a_kind, const char* a_family, const std::vector<int>& a_buckets, float a_d)
		{
			Blend b = Pick(a_kind, a_family, a_buckets, a_d);
			if (b.parts.size() == 2) {
				b.parts.erase(b.parts.begin() + (b.parts[0].second >= b.parts[1].second ? 1 : 0));
				b.parts[0].second = 1.0f;
			}
			return b;
		}

		std::vector<int> Buckets(const char* a_kind, const char* a_family)
		{
			const std::string k = a_kind, f = a_family;
			if (f == "up") {
				return k == "srelease" ? std::vector<int>{ 100, 300 } : std::vector<int>{ 50, 300 };
			}
			if (f == "down") {
				return (k == "takeoff" || k == "flight" || k == "surface" || k == "reception") ? std::vector<int>{ 50, 550 } : std::vector<int>{ 50, 300, 550 };
			}
			return k == "swingfl" ? std::vector<int>{ 50, 300 } : std::vector<int>{ 50, 300, 550 };
		}

		bool Start(RE::PlayerCharacter* a_player, bool a_manual, const Candidate* a_target = nullptr, const char* a_takeoff = "takeoff")
		{
			const Snapshot snap = Latest();
			const auto*    target = a_target ? a_target : LandingTarget(snap);
			if (!target) {
				return false;
			}
			Jump j;
			j.manual = a_manual;
			j.from = a_player->GetPosition();
			j.to = LandingPoint(*target, j.from);
			if (target->type == EdgeType::kHang) {
				// a ledge too high to land on: AC1 jumps "to surface" and catches it into a wall hang
				RE::NiPoint3 dir0 = target->point - j.from;
				dir0.z = 0.0f;
				const float l0 = std::sqrt(dir0.x * dir0.x + dir0.y * dir0.y);
				dir0 = l0 > 1.0f ? dir0 / l0 : RE::NiPoint3{ 0.0f, 1.0f, 0.0f };
				if (!LedgeRefine(target->point, dir0, j.hangEdge, j.hangFacing)) {
					return false;
				}
				j.hang = true;
				j.to = LedgeHangPosition(j.hangEdge, j.hangFacing);
			}
			j.type = target->type;
			if (target->type == EdgeType::kBar) {
				// a swing bar: AC1 flies "to swing" and catches it with the hands
				RE::NiPoint3 dir0 = target->point - j.from;
				dir0.z = 0.0f;
				const float  l0 = std::sqrt(dir0.x * dir0.x + dir0.y * dir0.y);
				dir0 = l0 > 1.0f ? dir0 / l0 : DirOf(a_player->data.angle.z);
				RE::NiPoint3 axis;
				if (!BarFrame(target->point, dir0, axis, j.barFacing)) {
					return false;
				}
				j.hangEdge = target->point;
				j.to = SwingHangPosition(j.hangEdge, j.barFacing, "swing_catch", 0.0f);
			} else if (target->type == EdgeType::kBeam || target->type == EdgeType::kPole) {
				j.to = target->point + RE::NiPoint3{ 0.0f, 0.0f, 2.0f };  // onto the top, at the near edge
				RE::NiPoint3 dir0 = target->point - j.from;
				dir0.z = 0.0f;
				const float l0 = std::sqrt(dir0.x * dir0.x + dir0.y * dir0.y);
				if (l0 > 1.0f) {
					j.to = j.to + dir0 / l0 * (0.2f * kUnits);
				}
			}
			const float dx = j.to.x - j.from.x, dy = j.to.y - j.from.y;
			const float dh = std::sqrt(dx * dx + dy * dy);
			j.dir = dh > 1.0f ? RE::NiPoint3{ dx / dh, dy / dh, 0.0f } : RE::NiPoint3{ std::sin(a_player->GetAngleZ()), std::cos(a_player->GetAngleZ()), 0.0f };
			j.yaw = std::atan2(j.dir.x, j.dir.y);
			const float d = dh / kUnits;
			const float dz = (j.to.z - j.from.z) / kUnits;

			if (g_packLoaded) {
				const char* family = dz > 0.6f ? "up" : (dz < -0.6f ? "down" : "front");
				const char* flightKind = j.hang ? "surface" : (j.type == EdgeType::kBar ? "swingfl" : "flight");
				j.takeoff = Pick(a_takeoff, family, Buckets(a_takeoff, family), d);
				if (j.takeoff.Empty()) {
					j.takeoff = Pick("takeoff", family, Buckets("takeoff", family), d);
				}
				j.flight = Pick(flightKind, family, Buckets(flightKind, family), d);
				if (j.flight.Empty()) {
					j.flight = Pick("flight", family, Buckets("flight", family), d);
				}
				if (!j.hang && j.type == EdgeType::kRoof) {
					j.reception = Nearest("reception", family, Buckets("reception", family), d);
				}
				j.animated = !j.takeoff.Empty() && !j.flight.Empty();
			}
			if (j.animated) {
				j.t1 = j.takeoff.Duration();
				// longer than AC1's longest item (5.5 m) or a big drop: the flight is stretched in time
				const float maxD = dz > 0.6f ? 3.0f : 5.5f;
				j.flightStretch = std::max({ 1.0f, d / maxD, std::sqrt(std::max(1.0f, -dz / 2.5f)) });
				j.t2 = j.flight.Duration() * j.flightStretch;
				j.tr = j.reception.Empty() ? 0.0f : j.reception.Duration();
				const auto a = j.takeoff.DispAt(1.0f);
				const auto b = j.flight.DispAt(1.0f);
				j.dispEnd = { a[0] + b[0], a[1] + b[1] };
			} else {
				// no clips: the P1 arc
				j.t1 = 0.0f;
				j.t2 = std::clamp(0.35f + 0.09f * d + (dz < 0.0f ? 0.06f * -dz : 0.0f), 0.45f, 1.2f);
				j.apex = g_settings.arcHeight * (0.45f + 0.07f * d + 0.35f * std::max(dz, 0.0f)) * kUnits;
			}
			j.phase = j.animated ? Phase::kTakeoff : Phase::kFlight;
			g_jump = j;
			logger::info("{} jump: {:.1f} m ahead, {:+.1f} m, {:.2f}+{:.2f} s ({}, {})", a_manual ? "target" : "free-run", d, dz,
				j.t1, j.t2, target->type == EdgeType::kBeam ? "beam" : (j.hang ? "ledge catch" : "roof edge"), j.animated ? "AC1 clips" : "arc");
			return true;
		}

		// AC1 HumanInAir__UpdateJumpMotion: the root follows the blended clip displacement, plus a linear correction
		// (target - animEnd) * t / T so it arrives exactly on the target.
		RE::NiPoint3 PathAt(float a_t)
		{
			const auto& j = g_jump;
			const float T = j.t1 + j.t2;
			const float s = std::clamp(a_t / T, 0.0f, 1.0f);
			if (!j.animated) {
				RE::NiPoint3 p = j.from + (j.to - j.from) * s;
				p.z += 4.0f * j.apex * s * (1.0f - s);
				return p;
			}
			std::array<float, 2> disp;
			if (a_t < j.t1) {
				disp = j.takeoff.DispAt(a_t / j.t1);
			} else {
				const auto a = j.takeoff.DispAt(1.0f);
				const auto b = j.flight.DispAt((a_t - j.t1) / j.t2);
				disp = { a[0] + b[0], a[1] + b[1] };
			}
			const RE::NiPoint3 animEnd = j.from + j.dir * (j.dispEnd[0] * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, j.dispEnd[1] * kUnits };
			const RE::NiPoint3 anim = j.from + j.dir * (disp[0] * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, disp[1] * kUnits };
			RE::NiPoint3       p = anim + (j.to - animEnd) * s;
			// AC1's items carry little lift; keep a minimum arc so long jumps don't read as a glide
			// up-jumps get extra lift so the feet clear the edge they land on
			const float rise = std::max(0.0f, (j.to.z - j.from.z) / kUnits);
			p.z += 4.0f * (g_settings.arcHeight - 1.0f + 0.25f + 0.25f * rise) * kUnits * s * (1.0f - s) * std::min(1.0f, (j.t2 + j.t1) / 0.6f);
			return p;
		}

		void Hold(RE::PlayerCharacter* a_player, const RE::NiPoint3& a_at, bool a_onGround)
		{
			a_player->SetPosition(a_at, true);
			a_player->data.angle.z = g_jump.yaw;
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
	}

	Settings& GetSettings() { return g_settings; }

	void Settings::Load()
	{
		char buf[16]{};
		auto get = [&](const char* k, const char* def) {
			GetPrivateProfileStringA("Freerun", k, def, buf, sizeof(buf), kIni);
			return std::string(buf);
		};
		overlay = get("bOverlay", "1") != "0";
		targetJumps = get("bTargetJumps", "1") != "0";
		requireSprint = get("bRequireSprint", "1") != "0";
		ac1Animations = get("bAC1Animations", "1") != "0";
		autoJump = get("bAutoJump", "1") != "0";
		ledges = get("bLedges", "1") != "0";
		p4 = get("bBeamsPolesWallRun", "1") != "0";
		hayHide = get("bHayHide", "1") != "0";
		pray = get("bPray", "1") != "0";
		prayCloseEyes = get("bPrayCloseEyes", "1") != "0";
		prayKey = static_cast<int>(std::strtol(get("iPrayKey", "0x30").c_str(), nullptr, 0));
		gaitSmoothing = std::clamp(static_cast<float>(std::atof(get("fGaitSmoothing", "0.30").c_str())), 0.0f, 1.0f);
		SetGaitSmoothing(gaitSmoothing);
		arcHeight = std::clamp(static_cast<float>(std::atof(get("fArcHeight", "1.0").c_str())), 0.2f, 3.0f);
		g_packLoaded = LoadPack();
	}

	void Settings::Save() const
	{
		auto put = [](const char* k, const std::string& v) { WritePrivateProfileStringA("Freerun", k, v.c_str(), kIni); };
		put("bOverlay", overlay ? "1" : "0");
		put("bTargetJumps", targetJumps ? "1" : "0");
		put("bRequireSprint", requireSprint ? "1" : "0");
		put("bAC1Animations", ac1Animations ? "1" : "0");
		put("bAutoJump", autoJump ? "1" : "0");
		put("bLedges", ledges ? "1" : "0");
		put("bBeamsPolesWallRun", p4 ? "1" : "0");
		put("bHayHide", hayHide ? "1" : "0");
		put("bPray", pray ? "1" : "0");
		put("bPrayCloseEyes", prayCloseEyes ? "1" : "0");
		put("iPrayKey", std::format("0x{:02X}", prayKey));
		put("fGaitSmoothing", std::format("{:.2f}", gaitSmoothing));
		SetGaitSmoothing(gaitSmoothing);
		put("fArcHeight", std::format("{:.2f}", arcHeight));
	}

	void NotifyJumpPressed() { g_jumpPressed = true; }

	bool TakeJumpPress() { return g_jumpPressed.exchange(false); }

	namespace
	{
		std::atomic<bool> g_rawSprint{ false };
	}
	void SetRawSprint(bool a_down) { g_rawSprint = a_down; }
	bool RawSprint() { return g_rawSprint; }

	bool StartJumpFrom(RE::PlayerCharacter* a_player, const Candidate* a_target, const char* a_takeoff)
	{
		return Start(a_player, false, a_target, a_takeoff);
	}

	namespace
	{
		std::array<std::atomic<float>, 6> g_raw{};
		float                              g_spTimer = 0.0f;
	}

	void SetRawMove(int a_axis, float a_value)
	{
		if (a_axis >= 0 && a_axis < 6) {
			g_raw[a_axis] = a_value;
		}
	}

	RE::NiPoint2 RawMove()
	{
		float x = g_raw[3] - g_raw[2] + g_raw[4];
		float y = g_raw[0] - g_raw[1] + g_raw[5];
		return { std::clamp(x, -1.0f, 1.0f), std::clamp(y, -1.0f, 1.0f) };
	}

	void SuppressSkyParkour(RE::PlayerCharacter* a_player, float a_delta)
	{
		g_spTimer = std::max(0.0f, g_spTimer - a_delta);
		bool ongoing = false;
		if (g_spTimer <= 0.0f && a_player->GetGraphVariableBool("SkyParkourOngoing", ongoing) && ongoing) {
			a_player->NotifyAnimationGraph("SkyParkour_Interrupt");
			g_spTimer = 0.15f;
			logger::info("SkyParkour move interrupted (an AC1 ledge move is running)");
		}
	}

	bool TargetJumpActive() { return g_jump.phase == Phase::kTakeoff || g_jump.phase == Phase::kFlight; }

	void TargetJumpUpdate(RE::PlayerCharacter* a_player, float a_delta)
	{
		bool inJump = false;
		a_player->GetGraphVariableBool("bInJumpState", inJump);
		auto& j = g_jump;
		g_cooldown = std::max(0.0f, g_cooldown - a_delta);
		const bool pressed = g_jumpPressed.exchange(false);

		// after a manual jump: make sure Skyrim's behavior graph leaves the jump (it can miss the landing because the
		// controller never really fell)
		if (j.settling) {
			j.settle += a_delta;
			auto* controller = a_player->GetCharController();
			const bool grounded = controller && controller->context.currentState == RE::hkpCharacterStateType::kOnGround;
			if (!inJump || j.settle > 1.5f) {
				j.settling = false;
			} else if (grounded && j.settle > 0.2f && j.settle - a_delta <= 0.2f) {
				a_player->NotifyAnimationGraph("JumpLand");
			} else if (j.settle > 0.6f && j.settle - a_delta <= 0.6f) {
				a_player->NotifyAnimationGraph("JumpLandEnd");
			} else if (j.settle > 1.0f && j.settle - a_delta <= 1.0f) {
				a_player->NotifyAnimationGraph("JumpLandFailSafe");
			}
		}

		switch (j.phase) {
		case Phase::kTakeoff:
		case Phase::kFlight:
			{
				j.t += a_delta;
				const float T = j.t1 + j.t2;
				if (j.t >= T && j.hang) {
					j.phase = Phase::kNone;
					j.t = 0.0f;
					LedgeBegin(a_player, j.hangEdge, j.hangFacing);
					break;
				}
				if (j.t >= T && j.type == EdgeType::kBar) {
					j.phase = Phase::kNone;
					SwingBegin(a_player, j.hangEdge, j.barFacing);
					break;
				}
				if (j.t >= T && (j.type == EdgeType::kBeam || j.type == EdgeType::kPole)) {
					j.phase = Phase::kNone;
					NarrowBegin(a_player, j.to, j.dir, j.type == EdgeType::kPole);
					break;
				}
				if (j.t >= T) {
					bool airborneInGraph = false;
					a_player->GetGraphVariableBool("bInJumpState", airborneInGraph);
					if (j.manual || airborneInGraph) {
						// Skyrim's jump is still running in the behavior graph: hand back a few cm above the target with a
						// small drop, so the character controller registers a real landing and the graph leaves the jump
						Hold(a_player, j.to + RE::NiPoint3{ 0.0f, 0.0f, 6.0f }, false);
						if (auto* controller = a_player->GetCharController()) {
							const float s = RE::bhkWorld::GetWorldScale();
							controller->SetLinearVelocityImpl(RE::hkVector4(0.0f, 0.0f, -250.0f * s, 0.0f));
						}
						j.settling = true;
						j.settle = 0.0f;
					} else {
						Hold(a_player, j.to, true);
					}
					j.t = 0.0f;
					j.phase = j.tr > 0.0f && g_settings.ac1Animations ? Phase::kReception : Phase::kNone;
					if (j.phase == Phase::kNone) {
						ClearPose();
					}
					break;
				}
				Hold(a_player, PathAt(j.t), false);
				if (j.hang) {
					SuppressSkyParkour(a_player, a_delta);
				}
				if (j.animated && g_settings.ac1Animations) {
					const float w = std::min(1.0f, j.t / kBlendIn);
					if (j.t < j.t1) {
						j.phase = Phase::kTakeoff;
						SetPose(j.takeoff, j.t / j.t1, w);
					} else {
						j.phase = Phase::kFlight;
						SetPose(j.flight, (j.t - j.t1) / j.t2, w);
					}
				}
				break;
			}
		case Phase::kReception:
			{
				// back on the ground, running: AC1's free-step reception, then hand back to the game's animation
				j.t += a_delta;
				if (j.t >= j.tr) {
					ClearPose();
					j.phase = Phase::kNone;
					break;
				}
				const float w = std::min(1.0f, (j.tr - j.t) / kBlendOut);
				SetPose(j.reception, j.t / j.tr, w);
				break;
			}
		default:
			if (LedgeActive() || NarrowActive() || SwingActive() || WallRunActive() || HayActive()) {
				break;
			}
			// the jump key, with a ledge in front: catch it straight away (before SkyParkour / FreeClimb climb it)
			if (pressed && !inJump && g_settings.ledges && g_settings.targetJumps && !LeapOfFaithArmed(a_player)) {
				Update(a_player);
				const Snapshot snap = Latest();
				if (const auto* t = LandingTarget(snap); t && t->type == EdgeType::kHang && Start(a_player, false, t)) {
					break;
				}
				// no catchable ledge: a wall too tall to catch straight ahead -> run up it (AC1 walling)
				if (const auto* t = LandingTarget(snap); g_settings.p4 && (!t || t->distance > 2.5f) && WallRunTry(a_player)) {
					break;
				}
			}
			if (inJump && !g_wasInJump && g_settings.targetJumps && !LeapOfFaithArmed(a_player)) {
				const bool sprinting = a_player->AsActorState()->IsSprinting();
				Update(a_player);
				if (sprinting || !g_settings.requireSprint) {
					Start(a_player, true);
				} else if (g_settings.ledges) {
					// AC1 grabs a ledge from any jump at it, not only from a run: a ledge in reach is caught without sprint
					const Snapshot snap = Latest();
					if (const auto* t = LandingTarget(snap); t && t->type == EdgeType::kHang) {
						Start(a_player, true, t);
					}
				}
			} else if (!inJump && g_settings.autoJump && g_settings.targetJumps && g_cooldown <= 0.0f &&
					   a_player->AsActorState()->IsSprinting() && !LeapOfFaithArmed(a_player)) {
				// AC1 free-run: sprinting, Altair jumps by himself at the edge of a drop, or at a step up he can't run up
				auto*      controller = a_player->GetCharController();
				const bool grounded = controller && controller->context.currentState == RE::hkpCharacterStateType::kOnGround;
				if (grounded && !GroundAhead(a_player, 0.7f, 1.0f)) {
					Update(a_player);
					const Snapshot snap = Latest();
					if (const auto* t = LandingTarget(snap); t && t->distance >= 1.0f) {
						Start(a_player, false, t);
						g_cooldown = 0.3f;
					}
				} else if (grounded) {
					const Snapshot snap = Latest();
					if (const auto* t = LandingTarget(snap);
						t && t->distance < 2.2f &&
						((t->type == EdgeType::kRoof && t->height > 0.8f && t->height < 2.6f) ||
							(t->type == EdgeType::kHang && t->height >= 2.0f && t->height < 3.1f))) {
						Start(a_player, false, t);
						g_cooldown = 0.3f;
					}
				}
			}
			break;
		}
		g_wasInJump = inJump;
	}
}
