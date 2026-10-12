#include "PosePlayer.h"

namespace Freerun
{
	namespace
	{
		constexpr auto kPack = "Data/SKSE/Plugins/AltairFreerun/AltairFreerun.pack";

		// gait smoothing (inertialization)
		float                         g_gaitSeconds = 0.3f;
		int                           g_lastGait = -1;
		float                         g_sinceGait = 10.0f;
		float                         g_offsetAge = 10.0f;
		float                         g_offsetSeconds = 0.18f;
		std::vector<RE::NiQuaternion> g_prevOutR, g_curR, g_offR;
		std::vector<RE::NiPoint3>     g_prevOutT, g_curT, g_offT;

		std::vector<std::string> g_bones;
		std::vector<Clip>        g_clips;

		// what to show (written by the jump state machine on the main thread, read in the animation hook)
		std::mutex g_poseLock;
		Blend      g_blend;
		float      g_u = 0.0f;
		float      g_weight = 0.0f;

		// live nodes of the third-person skeleton, found again whenever the 3D is rebuilt
		RE::NiAVObject*              g_root = nullptr;
		std::vector<RE::NiAVObject*> g_nodes;

		template <class T>
		bool Read(const std::vector<char>& a_data, std::size_t& a_at, T& a_out)
		{
			if (a_at + sizeof(T) > a_data.size()) {
				return false;
			}
			std::memcpy(&a_out, a_data.data() + a_at, sizeof(T));
			a_at += sizeof(T);
			return true;
		}

		bool ReadString(const std::vector<char>& a_data, std::size_t& a_at, std::string& a_out)
		{
			std::uint16_t n = 0;
			if (!Read(a_data, a_at, n) || a_at + n > a_data.size()) {
				return false;
			}
			a_out.assign(a_data.data() + a_at, n);
			a_at += n;
			return true;
		}

		RE::NiQuaternion Nlerp(const RE::NiQuaternion& a, RE::NiQuaternion b, float t)
		{
			if (a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z < 0.0f) {
				b = { -b.w, -b.x, -b.y, -b.z };
			}
			RE::NiQuaternion q{ a.w + (b.w - a.w) * t, a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t };
			const float      l = std::sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
			return l > 1e-6f ? RE::NiQuaternion{ q.w / l, q.x / l, q.y / l, q.z / l } : a;
		}

		void ToMatrix(const RE::NiQuaternion& q, RE::NiMatrix3& m)
		{
			const float x = q.x, y = q.y, z = q.z, w = q.w;
			m.entry[0][0] = 1 - 2 * (y * y + z * z);
			m.entry[0][1] = 2 * (x * y - z * w);
			m.entry[0][2] = 2 * (x * z + y * w);
			m.entry[1][0] = 2 * (x * y + z * w);
			m.entry[1][1] = 1 - 2 * (x * x + z * z);
			m.entry[1][2] = 2 * (y * z - x * w);
			m.entry[2][0] = 2 * (x * z - y * w);
			m.entry[2][1] = 2 * (y * z + x * w);
			m.entry[2][2] = 1 - 2 * (x * x + y * y);
		}

		RE::NiQuaternion FromMatrix(const RE::NiMatrix3& a_m)
		{
			const auto&      m = a_m.entry;
			RE::NiQuaternion q;
			const float      tr = m[0][0] + m[1][1] + m[2][2];
			if (tr > 0.0f) {
				const float s = std::sqrt(tr + 1.0f) * 2.0f;
				q = { 0.25f * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s };
			} else if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) {
				const float s = std::sqrt(1.0f + m[0][0] - m[1][1] - m[2][2]) * 2.0f;
				q = { (m[2][1] - m[1][2]) / s, 0.25f * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s };
			} else if (m[1][1] > m[2][2]) {
				const float s = std::sqrt(1.0f + m[1][1] - m[0][0] - m[2][2]) * 2.0f;
				q = { (m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25f * s, (m[1][2] + m[2][1]) / s };
			} else {
				const float s = std::sqrt(1.0f + m[2][2] - m[0][0] - m[1][1]) * 2.0f;
				q = { (m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25f * s };
			}
			return q;
		}

		// one clip's local transform of bone b at normalized time u
		void Sample(const Clip& a_c, std::size_t a_b, float a_u, RE::NiQuaternion& a_q, RE::NiPoint3& a_t)
		{
			const float       x = std::clamp(a_u, 0.0f, 1.0f) * static_cast<float>(a_c.frames - 1);
			const std::size_t f0 = static_cast<std::size_t>(x);
			const std::size_t f1 = std::min<std::size_t>(f0 + 1, a_c.frames - 1);
			const float       k = x - static_cast<float>(f0);
			const std::size_t n = g_bones.size();
			a_q = Nlerp(a_c.rot[f0 * n + a_b], a_c.rot[f1 * n + a_b], k);
			a_t = a_c.trans[f0 * n + a_b] + (a_c.trans[f1 * n + a_b] - a_c.trans[f0 * n + a_b]) * k;
		}

		void FindNodes(RE::NiAVObject* a_root)
		{
			if (a_root == g_root) {
				return;
			}
			g_root = a_root;
			g_nodes.assign(g_bones.size(), nullptr);
			std::size_t found = 0;
			for (std::size_t i = 1; i < g_bones.size(); ++i) {  // bone 0 (NPC Root) stays where the game puts it
				// the third-person camera follows the camera bones: leave them to the game (AC1's body motion would swing it)
				if (g_bones[i].starts_with("Camera")) {
					continue;
				}
				g_nodes[i] = a_root->GetObjectByName(RE::BSFixedString(g_bones[i].c_str()));
				found += g_nodes[i] != nullptr;
			}
			logger::info("pose player: {} of {} bones found on the player", found, g_bones.size() - 1);
		}
	}

	std::array<float, 2> Clip::DispAt(float a_u) const
	{
		if (disp.empty()) {
			return { 0.0f, 0.0f };
		}
		const float       x = std::clamp(a_u, 0.0f, 1.0f) * static_cast<float>(disp.size() - 1);
		const std::size_t f0 = static_cast<std::size_t>(x);
		const std::size_t f1 = std::min(f0 + 1, disp.size() - 1);
		const float       k = x - static_cast<float>(f0);
		return { disp[f0][0] + (disp[f1][0] - disp[f0][0]) * k, disp[f0][1] + (disp[f1][1] - disp[f0][1]) * k };
	}

	RE::NiPoint3 Clip::HandsAt(float a_u) const
	{
		if (hands.empty()) {
			return {};
		}
		const float       x = std::clamp(a_u, 0.0f, 1.0f) * static_cast<float>(hands.size() - 1);
		const std::size_t f0 = static_cast<std::size_t>(x);
		const std::size_t f1 = std::min(f0 + 1, hands.size() - 1);
		return hands[f0] + (hands[f1] - hands[f0]) * (x - static_cast<float>(f0));
	}

	void SetGaitSmoothing(float a_seconds) { g_gaitSeconds = std::max(0.0f, a_seconds); }

	namespace
	{
		RE::NiQuaternion Mul(const RE::NiQuaternion& a, const RE::NiQuaternion& b)
		{
			return { a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z, a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
				a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x, a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w };
		}
		RE::NiQuaternion Conj(const RE::NiQuaternion& q) { return { q.w, -q.x, -q.y, -q.z }; }

		// The game's own pose this frame -> eased toward it from where the last frame ended, after a gait switch.
		void StartOffset(std::size_t n);
		void ApplyOffset(std::size_t n);
		void Enclose(RE::NiAVObject* a_root);
		int   g_gaitCandidate = -1;
		float g_gaitStable = 0.0f;

		void SmoothGait(RE::PlayerCharacter* a_player, RE::NiAVObject* a_root, float a_delta, bool a_fromAC1)
		{
			// walk / run / sprint only (not "moving or not", which flips on every stop); a switch must hold 0.1 s
			const auto* st = a_player->AsActorState();
			const int   raw = st->IsSprinting() ? 3 : (st->IsWalking() ? 1 : 2);
			if (raw != g_gaitCandidate) {
				g_gaitCandidate = raw;
				g_gaitStable = 0.0f;
			} else {
				g_gaitStable += a_delta;
			}
			const int gait = (g_gaitStable >= 0.1f || g_lastGait < 0) ? g_gaitCandidate : g_lastGait;
			const std::size_t n = g_nodes.size();
			g_curR.resize(n);
			g_curT.resize(n);
			for (std::size_t b = 1; b < n; ++b) {
				if (g_nodes[b]) {
					g_curR[b] = FromMatrix(g_nodes[b]->local.rotate);
					g_curT[b] = g_nodes[b]->local.translate;
				}
			}
			g_offsetAge += a_delta;
			if (a_fromAC1 && g_prevOutR.size() == n) {
				StartOffset(n);  // an AC1 move just ended: ease from its last pose into the game's
				g_offsetSeconds = 0.2f;
			}
			if (gait != g_lastGait) {
				if (g_lastGait >= 0 && g_gaitSeconds > 0.0f && g_prevOutR.size() == n) {
					StartOffset(n);
					g_offsetSeconds = g_gaitSeconds;
				}
				g_lastGait = gait;
			}
			// also coming out of an AC1 move (landing, pull-up, prayer): ease from its last pose into the game's
			if (g_offsetAge < g_offsetSeconds) {
				ApplyOffset(n);
				RE::NiUpdateData update{};
				a_root->UpdateDownwardPass(update, 0);
				Enclose(a_root);
			} else {
				g_prevOutR = g_curR;
				g_prevOutT = g_curT;
			}
		}
	}

	float Clip::YawAt(float a_u) const
	{
		if (yaw.empty()) {
			return 0.0f;
		}
		const float x = std::clamp(a_u, 0.0f, 1.0f) * static_cast<float>(yaw.size() - 1);
		const auto  i = static_cast<std::size_t>(x);
		const auto  j = std::min(i + 1, yaw.size() - 1);
		return yaw[i] + (yaw[j] - yaw[i]) * (x - static_cast<float>(i));
	}

	float Blend::YawAt(float a_u) const
	{
		float y = 0.0f;
		for (const auto& [c, w] : parts) {
			y += c->YawAt(a_u) * w;
		}
		return y;
	}

	float Blend::Duration() const
	{
		float d = 0.0f;
		for (const auto& [c, w] : parts) {
			d += c->duration * w;
		}
		return d;
	}

	std::array<float, 2> Blend::DispAt(float a_u) const
	{
		std::array<float, 2> out{ 0.0f, 0.0f };
		for (const auto& [c, w] : parts) {
			const auto d = c->DispAt(a_u);
			out[0] += d[0] * w;
			out[1] += d[1] * w;
		}
		return out;
	}

	bool LoadPack()
	{
		std::ifstream f(kPack, std::ios::binary);
		if (!f) {
			logger::error("pose pack {} not found: AC1 jump animations off", kPack);
			return false;
		}
		const std::vector<char> data((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
		std::size_t             at = 4;
		std::uint32_t           nb = 0, nc = 0;
		const bool v3 = data.size() >= 8 && std::memcmp(data.data(), "AFR3", 4) == 0;
		if (data.size() < 8 || (!v3 && std::memcmp(data.data(), "AFR2", 4) != 0) || !Read(data, at, nb)) {
			logger::error("pose pack: bad header");
			return false;
		}
		g_bones.resize(nb);
		for (auto& b : g_bones) {
			if (!ReadString(data, at, b)) {
				return false;
			}
		}
		if (!Read(data, at, nc)) {
			return false;
		}
		g_clips.resize(nc);
		for (auto& c : g_clips) {
			if (!ReadString(data, at, c.name) || !Read(data, at, c.duration) || !Read(data, at, c.frames) || c.frames == 0) {
				logger::error("pose pack: bad clip");
				return false;
			}
			c.rot.resize(static_cast<std::size_t>(c.frames) * nb);
			c.trans.resize(c.rot.size());
			for (std::size_t i = 0; i < c.rot.size(); ++i) {
				float v[7];
				if (!Read(data, at, v)) {
					return false;
				}
				c.rot[i] = { v[3], v[0], v[1], v[2] };  // packed x y z w -> NiQuaternion(w, x, y, z)
				c.trans[i] = { v[4], v[5], v[6] };
			}
			c.disp.resize(c.frames);
			for (auto& d : c.disp) {
				if (!Read(data, at, d)) {
					return false;
				}
			}
			c.hands.resize(c.frames);
			for (auto& h : c.hands) {
				float v[3];
				if (!Read(data, at, v)) {
					return false;
				}
				h = { v[0], v[1], v[2] };
			}
			c.yaw.assign(c.frames, 0.0f);
			if (v3) {
				for (auto& y : c.yaw) {
					if (!Read(data, at, y)) {
						return false;
					}
				}
			}
		}
		logger::info("pose pack: {} AC1 clips on {} bones", g_clips.size(), g_bones.size());
		return true;
	}

	const Clip* FindClip(const std::string& a_name)
	{
		for (const auto& c : g_clips) {
			if (c.name == a_name) {
				return &c;
			}
		}
		return nullptr;
	}

	void SetPose(const Blend& a_blend, float a_u, float a_weight)
	{
		std::scoped_lock l(g_poseLock);
		g_blend = a_blend;
		g_u = a_u;
		g_weight = std::clamp(a_weight, 0.0f, 1.0f);
	}

	void ClearPose()
	{
		std::scoped_lock l(g_poseLock);
		g_blend.parts.clear();
		g_weight = 0.0f;
	}

	namespace
	{
		float           g_camWeight = 0.0f;
		const Clip*     g_xfadeKey = nullptr;
		RE::NiAVObject* g_cam3 = nullptr;
		RE::NiAVObject* g_camCtrl = nullptr;
		RE::NiAVObject* g_camRoot = nullptr;

		void HoldCamera(RE::NiAVObject* a_root)
		{
			if (a_root != g_camRoot) {
				g_camRoot = a_root;
				g_cam3 = a_root->GetObjectByName("Camera3rd [Cam3]");
				g_camCtrl = a_root->GetObjectByName("Camera Control");
			}
			if (g_camWeight <= 0.0f) {
				return;
			}
			// only the camera's anchor height is held (its rotation belongs to the camera mods / the game)
			if (g_cam3) {
				g_cam3->local.translate = g_cam3->local.translate + (RE::NiPoint3{ 0.0f, 0.0f, 121.0f } - g_cam3->local.translate) * g_camWeight;
			}
		}

		// Skyrim culls a mesh by bounds computed from its own animation; after re-posing, the bounds of everything
		// under the skeleton are set to enclose the posed bones (as Faith Runner's Body does), so it never pops out
		void Enclose(RE::NiAVObject* a_root)
		{
			RE::NiPoint3 centre{};
			int          n = 0;
			for (auto* node : g_nodes) {
				if (node) {
					centre += node->world.translate;
					++n;
				}
			}
			if (!n) {
				return;
			}
			centre = centre / static_cast<float>(n);
			float radius = 0.0f;
			for (auto* node : g_nodes) {
				if (node) {
					radius = std::max(radius, node->world.translate.GetDistance(centre));
				}
			}
			radius += 80.0f;
			std::function<void(RE::NiAVObject*)> visit = [&](RE::NiAVObject* a_obj) {
				if (a_obj->worldBound.radius < radius || a_obj->worldBound.center.GetDistance(centre) > 1.0f) {
					a_obj->worldBound.center = centre;
					a_obj->worldBound.radius = std::max(a_obj->worldBound.radius, radius);
				}
				if (auto* node = a_obj->AsNode()) {
					for (auto& child : node->GetChildren()) {
						if (child) {
							visit(child.get());
						}
					}
				}
			};
			visit(a_root);
		}

		// capture the jump between what was shown last frame (g_prevOut*) and the new pose (g_cur*) as an offset
		void StartOffset(std::size_t n)
		{
			g_offR.resize(n);
			g_offT.resize(n);
			for (std::size_t b = 1; b < n; ++b) {
				auto q = Mul(g_prevOutR[b], Conj(g_curR[b]));
				if (q.w < 0.0f) {
					q = { -q.w, -q.x, -q.y, -q.z };
				}
				g_offR[b] = q;
				g_offT[b] = g_prevOutT[b] - g_curT[b];
			}
			g_offsetAge = 0.0f;
		}

		// write g_cur* (plus the decaying offset) onto the nodes and remember it as the last shown pose
		void ApplyOffset(std::size_t n)
		{
			const float x = g_offsetSeconds > 0.0f ? std::min(1.0f, g_offsetAge / g_offsetSeconds) : 1.0f;
			const float w = (g_offR.size() == n) ? 1.0f - x * x * (3.0f - 2.0f * x) : 0.0f;
			const RE::NiQuaternion id{ 1.0f, 0.0f, 0.0f, 0.0f };
			g_prevOutR.resize(n);
			g_prevOutT.resize(n);
			for (std::size_t b = 1; b < n; ++b) {
				if (!g_nodes[b]) {
					continue;
				}
				RE::NiQuaternion q = g_curR[b];
				RE::NiPoint3     t = g_curT[b];
				if (w > 0.0f) {
					q = Mul(Nlerp(id, g_offR[b], w), q);
					t = t + g_offT[b] * w;
				}
				ToMatrix(q, g_nodes[b]->local.rotate);
				g_nodes[b]->local.translate = t;
				g_prevOutR[b] = q;
				g_prevOutT[b] = t;
			}
		}
	}

	void ApplyPose(RE::PlayerCharacter* a_player, float a_delta)
	{
		Blend blend;
		float u = 0.0f, weight = 0.0f;
		{
			std::scoped_lock l(g_poseLock);
			blend = g_blend;
			u = g_u;
			weight = g_weight;
		}
		auto* root = a_player->Get3D(false);
		if (!root || g_bones.empty()) {
			return;
		}
		FindNodes(root);
		const bool active = !blend.Empty() && weight > 0.0f;
		// the camera follows Camera3rd / Camera Control: while an AC1 move plays they are held at rest (the
		// game's own jump / fall animation underneath would bob the camera), easing in and out with the move
		g_camWeight += std::clamp((active ? 1.0f : 0.0f) - g_camWeight, -a_delta / 0.25f, a_delta / 0.25f);
		HoldCamera(root);
		if (!active) {
			const bool fromAC1 = g_xfadeKey != nullptr;
			g_xfadeKey = nullptr;
			SmoothGait(a_player, root, a_delta, fromAC1);
			return;
		}
		g_lastGait = -1;  // an AC1 pose is playing: the next gait is a fresh start
		const std::size_t n = g_nodes.size();
		g_curR.resize(n);
		g_curT.resize(n);
		for (std::size_t b = 1; b < n; ++b) {
			auto* node = g_nodes[b];
			if (!node) {
				continue;
			}
			// weighted blend of the clips (AC1's item weights), then of that with the game's own pose
			RE::NiQuaternion q{};
			RE::NiPoint3     t{};
			float            acc = 0.0f;
			for (const auto& [clip, w] : blend.parts) {
				if (w <= 0.0f) {
					continue;
				}
				RE::NiQuaternion cq;
				RE::NiPoint3     ct;
				Sample(*clip, b, u, cq, ct);
				q = acc == 0.0f ? cq : Nlerp(q, cq, w / (acc + w));
				t = acc == 0.0f ? ct : t + (ct - t) * (w / (acc + w));
				acc += w;
			}
			if (weight < 1.0f) {
				q = Nlerp(FromMatrix(node->local.rotate), q, weight);
				t = node->local.translate + (t - node->local.translate) * weight;
			}
			g_curR[b] = q;
			g_curT[b] = t;
		}
		// a new clip (catch -> hang -> shimmy -> pull-up ...): ease out of the last pose instead of cutting to it
		const Clip* key = blend.parts.front().first;
		if (key != g_xfadeKey) {
			// a new clip, or the first AC1 clip after the game's own animation (e.g. the dive into the haystack):
			// ease out of whatever was shown last frame instead of cutting to the new pose
			if (g_prevOutR.size() == n) {
				StartOffset(n);
				g_offsetSeconds = g_xfadeKey ? 0.18f : 0.3f;
			}
			g_xfadeKey = key;
		}
		g_offsetAge += a_delta;
		ApplyOffset(n);
		RE::NiUpdateData update{};
		root->UpdateDownwardPass(update, 0);
		Enclose(root);
	}
}
