#include "EdgeFinder.h"

namespace Freerun
{
	namespace
	{
		constexpr float kUnits = 70.0f;  // game units per metre

		// AC1 JumpZones 0x1A2BF40 (via AC1-Movement-Rewritten jump_candidates.rs::ZONES).
		using Poly = std::vector<std::array<float, 2>>;
		const std::array<Poly, 13> kZones{ {
			{ { 0.5f, -5.0f }, { 0.5f, 0.2f }, { 3.5f, 0.6f }, { 4.7f, 0.3f }, { 6.0f, -0.8f }, { 7.5f, -3.0f }, { 7.5f, -5.0f } },
			{ { 0.5f, -5.0f }, { 0.5f, 1.3f }, { 3.5f, 1.3f }, { 4.7f, 0.8f }, { 6.0f, -0.5f }, { 8.0f, -3.0f }, { 8.0f, -5.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 2.5f }, { 3.5f, 2.5f }, { 5.0f, 1.5f }, { 6.5f, -0.5f }, { 8.5f, -3.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 3.0f }, { 3.5f, 3.0f }, { 5.3f, 1.8f }, { 7.0f, -0.5f }, { 9.0f, -3.0f } },
			{ { 0.5f, -5.0f }, { 0.5f, 1.3f }, { 4.0f, 1.3f }, { 5.2f, 0.8f }, { 6.5f, -0.5f }, { 8.5f, -3.0f }, { 8.5f, -5.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 2.5f }, { 4.0f, 2.5f }, { 5.5f, 1.5f }, { 7.0f, -0.5f }, { 9.0f, -3.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 3.0f }, { 4.0f, 3.0f }, { 5.8f, 1.8f }, { 7.5f, -0.5f }, { 9.5f, -3.0f } },
			{ { 0.5f, -4.3f }, { 0.5f, 2.0f }, { 3.5f, 2.0f }, { 4.7f, 1.5f }, { 6.0f, 0.2f }, { 7.0f, -2.3f }, { 7.0f, -4.3f } },
			{ { 0.5f, -2.3f }, { 0.5f, 3.2f }, { 3.5f, 3.2f }, { 5.0f, 2.3f }, { 6.5f, 0.2f }, { 7.5f, -2.3f } },
			{ { 0.5f, -2.3f }, { 0.5f, 3.7f }, { 3.5f, 3.7f }, { 5.3f, 2.5f }, { 7.0f, 0.2f }, { 8.0f, -2.3f } },
			{ { 0.5f, -5.0f }, { 0.5f, 0.0f }, { 1.0f, -0.2f }, { 2.0f, -1.0f }, { 3.0f, -3.0f }, { 3.0f, -5.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 1.5f }, { 1.0f, 1.3f }, { 2.25f, -0.3f }, { 3.5f, -3.0f } },
			{ { 0.5f, -3.0f }, { 0.5f, 2.5f }, { 1.0f, 2.3f }, { 2.5f, 1.8f }, { 4.0f, -3.0f } },
		} };

		std::mutex g_lock;
		Snapshot   g_latest;

		struct Hit
		{
			bool         hit{ false };
			RE::NiPoint3 point;
			RE::NiPoint3 normal;
		};

		// One Havok ray (game units in and out), static world only (the LOS layer ignores actors and clutter).
		Hit Ray(RE::bhkWorld* a_world, const RE::NiPoint3& a_from, const RE::NiPoint3& a_to)
		{
			Hit             out;
			const float     s = RE::bhkWorld::GetWorldScale();
			RE::bhkPickData pick{};
			pick.rayInput.from = RE::hkVector4(a_from.x * s, a_from.y * s, a_from.z * s, 0.0f);
			pick.rayInput.to = RE::hkVector4(a_to.x * s, a_to.y * s, a_to.z * s, 0.0f);
			pick.rayInput.enableShapeCollectionFilter = true;
			pick.rayInput.filterInfo.SetCollisionLayer(RE::COL_LAYER::kLOS);
			if (!a_world->PickObject(pick) || !pick.rayOutput.HasHit()) {
				return out;
			}
			const float f = pick.rayOutput.hitFraction;
			out.hit = true;
			out.point = a_from + (a_to - a_from) * f;
			out.normal = { pick.rayOutput.normal.quad.m128_f32[0], pick.rayOutput.normal.quad.m128_f32[1],
				pick.rayOutput.normal.quad.m128_f32[2] };
			return out;
		}

		// The top surface under (x, y) between z_hi and z_lo; z = -inf when none.
		Hit Down(RE::bhkWorld* a_world, float a_x, float a_y, float a_zHi, float a_zLo)
		{
			return Ray(a_world, { a_x, a_y, a_zHi }, { a_x, a_y, a_zLo });
		}

		RE::NiPoint3 Flat(RE::NiPoint3 v)
		{
			v.z = 0.0f;
			const float l = std::sqrt(v.x * v.x + v.y * v.y);
			return l > 1e-4f ? v / l : RE::NiPoint3{ 0.0f, 1.0f, 0.0f };
		}
	}

	bool InZone(int a_slot, float a_distance, float a_height)
	{
		const auto& poly = kZones[static_cast<std::size_t>(std::clamp(a_slot, 0, 12))];
		bool        inside = false;
		for (std::size_t i = 0, n = poly.size(); i < n; ++i) {
			const auto& a = poly[i];
			const auto& b = poly[(i + 1) % n];
			if ((a[1] > a_height) != (b[1] > a_height)) {
				const float t = (a_height - a[1]) / (b[1] - a[1]);
				if (a_distance < a[0] + t * (b[0] - a[0])) {
					inside = !inside;
				}
			}
		}
		return inside;
	}

	bool CastRay(const RE::NiPoint3& a_from, const RE::NiPoint3& a_to, RE::NiPoint3* a_hit, RE::NiPoint3* a_normal)
	{
		auto* player = RE::PlayerCharacter::GetSingleton();
		auto* cell = player ? player->GetParentCell() : nullptr;
		auto* world = cell ? cell->GetbhkWorld() : nullptr;
		if (!world) {
			return false;
		}
		const Hit h = Ray(world, a_from, a_to);
		if (h.hit) {
			if (a_hit) {
				*a_hit = h.point;
			}
			if (a_normal) {
				*a_normal = h.normal;
			}
		}
		return h.hit;
	}

	bool GroundAhead(RE::PlayerCharacter* a_player, float a_ahead, float a_drop)
	{
		auto* cell = a_player->GetParentCell();
		auto* world = cell ? cell->GetbhkWorld() : nullptr;
		if (!world) {
			return true;
		}
		const RE::NiPoint3 feet = a_player->GetPosition();
		const float        yaw = a_player->GetAngleZ();
		const RE::NiPoint3 p = feet + RE::NiPoint3{ std::sin(yaw), std::cos(yaw), 0.0f } * (a_ahead * kUnits);
		return Down(world, p.x, p.y, feet.z + 0.5f * kUnits, feet.z - a_drop * kUnits).hit;
	}

	void Update(RE::PlayerCharacter* a_player)
	{
		Snapshot snap;
		auto*    cell = a_player ? a_player->GetParentCell() : nullptr;
		auto*    world = cell ? cell->GetbhkWorld() : nullptr;
		if (!world) {
			std::scoped_lock l(g_lock);
			g_latest = std::move(snap);
			return;
		}

		const RE::NiPoint3 feet = a_player->GetPosition();
		snap.origin = feet;
		const float        yaw = a_player->GetAngleZ();
		const RE::NiPoint3 fwd{ std::sin(yaw), std::cos(yaw), 0.0f };
		const RE::NiPoint3 right{ fwd.y, -fwd.x, 0.0f };

		// AC1 picks a zone slot by jump kind and speed; P0 approximation: walk 0, run 1, sprint 4.
		const bool sprint = a_player->AsActorState()->IsSprinting();
		const bool running = a_player->AsActorState()->IsWalking() == false && a_player->IsMoving();
		const int  slot = sprint ? 4 : (running ? 1 : 0);

		const float zHi = feet.z + 4.0f * kUnits;
		const float zLo = feet.z - 6.0f * kUnits;
		const RE::NiPoint3 chest = feet + RE::NiPoint3{ 0.0f, 0.0f, 1.2f * kUnits };

		// Rows of down-rays straight ahead, 0.5 m apart, in three lanes. An edge is where the top surface steps up by
		// more than 0.6 m (the near edge of something to land on or grab) or the ground falls away and comes back
		// (the far side of a gap).
		for (float lane : { -0.75f, 0.0f, 0.75f }) {
			float prevZ = feet.z;
			bool  prevHit = true;
			for (float d = 1.0f; d <= 9.5f; d += 0.25f) {  // 25 cm: poles are 40 cm across
				const RE::NiPoint3 p = feet + fwd * (d * kUnits) + right * (lane * kUnits);
				const Hit          h = Down(world, p.x, p.y, zHi, zLo);
				const float        z = h.hit ? h.point.z : zLo;
				const bool         walkable = h.hit && h.normal.z > 0.7f;
				if (walkable && (!prevHit || z - prevZ > 0.6f * kUnits || prevZ - z > 1.0f * kUnits && d > 1.5f)) {
					// refine the edge between d - 0.5 and d: find where this top surface starts
					float lo = d - 0.25f, hi = d;
					for (int it = 0; it < 4; ++it) {
						const float        mid = 0.5f * (lo + hi);
						const RE::NiPoint3 q = feet + fwd * (mid * kUnits) + right * (lane * kUnits);
						const Hit          hm = Down(world, q.x, q.y, z + 0.3f * kUnits, z - 0.3f * kUnits);
						(hm.hit && hm.normal.z > 0.7f ? hi : lo) = mid;
					}
					const RE::NiPoint3 edge = feet + fwd * (hi * kUnits) + right * (lane * kUnits);
					Candidate          c;
					c.point = { edge.x, edge.y, z };
					c.wallNormal = fwd * -1.0f;
					c.distance = hi;
					c.height = (z - feet.z) / kUnits;

					// room on top? (AC1's first classification ray)
					const RE::NiPoint3 top = c.point + fwd * (0.3f * kUnits) + RE::NiPoint3{ 0.0f, 0.0f, 0.15f * kUnits };
					const bool         room = !Ray(world, top, top + RE::NiPoint3{ 0.0f, 0.0f, 1.7f * kUnits }).hit;
					// narrow? the surface drops away again within 0.6 m
					const RE::NiPoint3 past = c.point + fwd * (0.6f * kUnits);
					const Hit          beyond = Down(world, past.x, past.y, z + 0.3f * kUnits, z - 1.0f * kUnits);
					const bool         narrow = !beyond.hit;
					// clear line of sight from the chest (third ray)
					const bool sight = !Ray(world, chest, c.point + RE::NiPoint3{ 0.0f, 0.0f, 0.3f * kUnits }).hit;

					c.type = narrow ? EdgeType::kBeam : (room && c.height < 2.0f ? EdgeType::kRoof : EdgeType::kHang);
					if (narrow) {
						// narrow across too -> a pole top; narrow and above head height -> a bar to swing on
						const RE::NiPoint3 mid = c.point + fwd * (0.15f * kUnits);
						const bool         l = Down(world, mid.x - right.x * 0.45f * kUnits, mid.y - right.y * 0.45f * kUnits, z + 0.2f * kUnits, z - 0.2f * kUnits).hit;
						const bool         r = Down(world, mid.x + right.x * 0.45f * kUnits, mid.y + right.y * 0.45f * kUnits, z + 0.2f * kUnits, z - 0.2f * kUnits).hit;
						if (c.height >= 1.4f) {
							c.type = EdgeType::kBar;
						} else if (!l && !r) {
							c.type = EdgeType::kPole;
						}
					}
					// ledges to catch use AC1's taller reach zones (catch items reach up to 3 m: slots 3 / 6)
					const bool hands = c.type == EdgeType::kHang || c.type == EdgeType::kBar;
					c.inReach = sight && (hands ? InZone(sprint ? 6 : 3, c.distance, c.height) : InZone(slot, c.distance, c.height));
					// AC1 priority: nearest roof edge in front, then the highest other target
					// AC1's priorities (scorer 0xE96BF0): the nearest roof / beam / pole in front first, then the highest
					// other target (ledges, bars), and only then targets well below (the ground in a gap)
					const bool landable = c.type == EdgeType::kRoof || c.type == EdgeType::kBeam || c.type == EdgeType::kPole;
					c.score = !c.inReach        ? -1000.0f :
					          c.height < -0.8f ? 20.0f - c.distance - std::abs(lane) :
					          landable          ? 100.0f - c.distance - std::abs(lane) :
					                              50.0f + c.height - 0.5f * std::abs(lane);
					snap.candidates.push_back(c);
				}
				prevZ = z;
				prevHit = h.hit;
			}
		}

		// swing bars: a stack of forward rays above head height; something thin (hit at one height, open space
		// 20 cm above and below it at the same distance) is a bar to catch with the hands
		{
			float prevD = -1.0f;
			for (float h = 1.4f; h <= 3.4f; h += 0.1f) {
				const RE::NiPoint3 from = feet + RE::NiPoint3{ 0.0f, 0.0f, h * kUnits };
				const Hit          hit = Ray(world, from, from + fwd * (6.5f * kUnits));
				if (!hit.hit) {
					prevD = -1.0f;
					continue;
				}
				const float d = (hit.point - from).Length() / kUnits;
				const Hit   above = Ray(world, from + RE::NiPoint3{ 0.0f, 0.0f, 0.2f * kUnits }, from + RE::NiPoint3{ 0.0f, 0.0f, 0.2f * kUnits } + fwd * ((d + 0.3f) * kUnits));
				const Hit   below = Ray(world, from - RE::NiPoint3{ 0.0f, 0.0f, 0.2f * kUnits }, from - RE::NiPoint3{ 0.0f, 0.0f, 0.2f * kUnits } + fwd * ((d + 0.3f) * kUnits));
				if (above.hit || below.hit || std::abs(d - prevD) < 0.05f) {
					prevD = d;
					continue;
				}
				// its top
				const RE::NiPoint3 in = hit.point + fwd * (0.04f * kUnits);
				const Hit          top = Down(world, in.x, in.y, hit.point.z + 0.25f * kUnits, hit.point.z - 0.25f * kUnits);
				if (!top.hit) {
					continue;
				}
				Candidate c;
				c.point = { in.x, in.y, top.point.z };
				c.wallNormal = fwd * -1.0f;
				c.distance = d;
				c.height = (top.point.z - feet.z) / kUnits;
				c.type = EdgeType::kBar;
				c.inReach = InZone(sprint ? 6 : 3, c.distance, c.height) && !Ray(world, chest, c.point - RE::NiPoint3{ 0.0f, 0.0f, 0.1f * kUnits }).hit;
				c.score = c.inReach ? 55.0f + c.height : -1000.0f;
				snap.candidates.push_back(c);
				break;
			}
		}

		float best = -1.0f;
		for (int i = 0; i < static_cast<int>(snap.candidates.size()); ++i) {
			if (snap.candidates[i].score > best) {
				best = snap.candidates[i].score;
				snap.chosen = i;
			}
		}
		std::scoped_lock l(g_lock);
		g_latest = std::move(snap);
	}

	Snapshot Latest()
	{
		std::scoped_lock l(g_lock);
		return g_latest;
	}
}
