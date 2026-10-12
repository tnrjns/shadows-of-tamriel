# AC1 free-running in Skyrim — plan

Goal: Altaïr free-runs in Skyrim the way he does in AC1. Hold the free-run button, run at a gap, and he jumps
**from one point to another**: roof edge to roof edge, onto beams, up to ledges he can hang from. Each jump uses
AC1's own animations and lands exactly where it should.

This plan builds on what already works (native Skyrim character, our OAR locomotion and parkour animations, the
leap of faith) and on two references on this machine. Both are only read, never modified:

- **AC1-Movement-Rewritten** (your friend's port): AC1's free-run rules, reverse-engineered from the game, with
  addresses. Most numbers below come from it.
- **faith-runner / Corvo Skyrim**: a working Skyrim SKSE + CommonLibSSE-NG build setup (VS 2026 Build Tools,
  vcpkg, CommonLibSSE-NG) and a proven "drive the player from a plugin" approach.

The old AC1 bridge (hidden Bevy process streaming Skyrim collision) is **not** reused. This plan stays native:
Skyrim's own character, physics and camera, with AC1 logic added where Skyrim has none.

---

## 1. How AC1 actually does it

The big surprise: **AC1 jumps are not physics.** (`player/air.rs`, RE/04)

1. **Find candidates.** Every frame while free-running, the game looks for *guidance edges* in a box in front of
   Altaïr. Guidance edges are hand-placed markup in AC1's levels: roof edges, ledges, beams, poles, haystacks.
   On each edge it takes the point the forward line meets (`Human__QueryJumpCandidates`).
2. **Classify each point** with three rays: room on top? what's below? clear line of sight?
3. **Test reach.** Each point is checked against **13 side-profile reach zones**: polygons of (distance ahead,
   height above the feet). For example, slot 0 reaches 7.5 m out, 0.6 m up at 3.5 m, and 5 m down. The full
   table is in `jump_candidates.rs::ZONES`.
4. **Score and pick one.** Prefer the nearest roof edge in front, then the highest other target, then targets
   below or behind.
5. **Jump = two clips back to back.**
   - A **takeoff** clip: 40 variants, 5 direction groups × {front 0.5 / 3 / 5.5 m, down 0.5 / 3 / 5.5 m,
     up 0.5 / 3 m}.
   - Then a **flight** clip, chosen by target type: free-step (edge / roof), beam, hang, surface, swing,
     haystack, assassinate.
   - Clips are **blended by distance and height**. The root follows their combined animation motion, plus a
     **linear correction** `(target − animEnd) · t / (T1 + T2)`. So he always arrives *exactly* on the target
     (checked within 1 cm).
6. **Arrival = a reception clip.**
   - Free-step landing on an edge (24 clips: 12 normal, 12 fast).
   - Beam mount.
   - Catch into a hang (`*_to_hangfree / hangknee / hangwaist / hangwall`).
   - Or a ground landing chosen by drop height and speed.
7. **Real physics only for:**
   - **Over-drops.** A target more than 5 m below: aim 5 m down, then free fall at g = 9.8 with steering
     ≤ 15 m/s.
   - **Plain falls.** Drift decays at 4 m/s², max 5 m/s.
   - **Landing damage.** A total drop over 3 m gives a damage landing or a damage roll.

AC1 clips we can extract already (`ac1_anim_names.txt`):

| Clip family | Count |
|---|---|
| `*_to_air` takeoffs | 224 |
| `air_*_to_freestep` flights / receptions | 87 |
| `*to_hang*` catches | 63 |
| `beam_*` | 167 |
| `walling*` (wall run up) | 43 |
| landings | 79 |
| swing | 91 |

## 2. What Skyrim gives us (and doesn't)

| Need | Skyrim / installed mods |
|---|---|
| Ground movement | Native, with our AC1 OAR locomotion. **Done.** |
| Vault / climb small obstacles | SkyParkour with our AC1 animations. **Done.** |
| Wall climbing | FreeClimb (AC1 animations made, currently off) |
| Leap of faith | Our haystack system. **Done.** |
| **Guidance edges** | **None.** Skyrim has collision only. We must *derive* edges. |
| **Target-driven jumps** | **None.** Skyrim jumps are ballistic. We must take over motion during a jump. |
| Chained AC1 clips (takeoff → flight → reception) | The behavior graph can't express it. We need our own clip player. |

## 3. Architecture: `AltairFreerun.dll` (new SKSE plugin, C++ / CommonLibSSE-NG)

```
            ┌──────────────── every frame (player update hook) ────────────────┐
 input  ──► │ FreerunState: Ground → Takeoff → Flight → Reception / Hang / Fall │
            │      │              ▲                                            │
            │      ▼              │                                            │
            │ EdgeFinder ──► Candidates ──► Scorer (AC1 zones + priorities)    │
            │  (Havok rays,    (grab points,                                   │
            │   cached per      type, flags)                                   │
            │   cell)                                                          │
            │      │                                                           │
            │      ▼                                                           │
            │ MotionDriver: root = blended clip motion + linear correction     │
            │   → character controller velocity / position                     │
            │ PosePlayer: samples AC1 clips (retargeted to Skyrim skeleton)    │
            │   → writes bone transforms (like FreeClimb / Faith Runner's Body) │
            └──────────────────────────────────────────────────────────────────┘
 Settings / debug overlay: SKSE Menu Framework ("Altair AC1" page + HUD element)
```

### 3.1 EdgeFinder: making AC1 guidance edges out of Skyrim collision

AC1 has its edges placed by hand. We find them at runtime, the way AC1's own "geometry fallback" does for
untagged boxes (RE/06 §8):

1. **Probe grid.** While free-running, cast a fan of rays ahead of the player:
   - **Down rays** on a 0.5 m grid out to 9.5 m (AC1's furthest zone) to find **top surfaces**.
   - **Horizontal rays** at shin, waist and head height to find **walls**.
2. **An edge** is a top surface that drops away on one side, by more than 1 m or into a wall face. Walk along it
   with more down rays to get the edge segment and its normal. That gives exactly AC1's guidance object: two
   vertices, the top normal and the wall normal.
3. **Classify like AC1:**
   - **Roof / free-step edge:** walkable top, room on top (a capsule fits).
   - **Hang ledge:** wall below, no room on top, or the top is out of reach.
   - **Beam / pole:** top narrower than 0.6 m with a drop on both sides.
   - **Haystack:** our ACTI.
4. **Cache** edges per loaded cell, so we only re-probe new areas.
5. **Optional, later:** bake edges offline per worldspace, the way Faith Runner's parkour tool bakes
   `FaithParkour/<worldspace>.bin`, for cities like Solitude and Whiterun. Runtime probing stays as the fallback.

Skyrim API: `TESObjectCELL::GetbhkWorld()` → `bhkWorld::PickObject(bhkPickData&)`, with a collision filter
that hits static, anim-static and terrain only.

### 3.2 Scorer: a straight port

- **`ZONES`:** the 13 polygons, copied from the friend's port.
- **The three classification rays.**
- **The priority order:** nearest roof edge in front > highest other > below / behind.
- **Input:** stick direction relative to the camera, as in AC1. The free-run button is the "high profile + legs"
  chord: hold sprint + jump.

### 3.3 MotionDriver: target-locked jumps

At takeoff, store the start point P0, the target PT, and the chosen takeoff and flight clips with their weights.
Each frame:

- **Root position:**
  `p(t) = P0 + blendedRootMotion(t) + (PT − P0 − blendedRootMotion(T)) · t / T`
- **Apply it** by setting the character controller's velocity to `(p(t+dt) − pos) / dt`. This keeps Skyrim's
  collision response, which is safer than teleporting.
- **Free fall** only in the over-drop tail and on plain falls, using AC1's numbers.
- **Fall damage** is AC1's: drops over 3 m mean a damage roll.

### 3.4 PosePlayer: AC1 clips without behavior edits

Skyrim's behavior graph can't chain *takeoff → flight → reception* with blending. Like FreeClimb, we sample
our own clips:

- **Offline:** reuse our Blender retarget pipeline (`retarget_ac1_v2.py`) to bake each AC1 clip onto the
  Skyrim skeleton. Write a compact pack: per-frame local bone rotations and the root track, as the binary
  `ac1_freerun.pack`.
- **Runtime:** while FreerunState ≠ Ground, blend the clips (takeoff/flight weights, 0.1–0.2 s cross-fades) and
  write the local transforms onto the player's 3rd- and 1st-person skeletons after the animation update.
  Faith Runner's `Body.cpp` is the reference for where to hook.
- **Hand back** to the behavior graph (our OAR locomotion) on reception, with a short blend.

### 3.5 Hangs, beams, wall runs (later phases)

- **Hang:** AC1's ledge context. Root 1.1 m below the hands, 0.5 m out; shimmy in 0.6 m steps; pull-up if
  there's standing room; drop. Clips: `*_to_hang*`, hang idle / shimmy / pull-up.
- **Beam:** constrain the root to the beam line, stop 0.3 m before the end, step off ends with free space.
- **Wall run up (walling):** run at a wall, AC1's `wallingfront_*` clips, ledge probe at the top.
- **Wall climbing:** keep FreeClimb (its AC1 animation pack exists) and hand off to it, or port AC1's climb grid
  (0.75 m columns × 0.6 m rows) later.

## 4. Phases

| Phase | Deliverable | You'll see in game |
|---|---|---|
| **P0 — Edge finder + overlay** (built, untested) | SKSE plugin skeleton (CommonLibSSE-NG), Havok probes, AC1 candidate scoring, debug overlay through SKSE Menu Framework's HUD hook | Coloured markers on every ledge / roof edge / beam he *could* jump to; the chosen target highlighted. No movement change yet. |
| **P1 — Target-locked jumps** (built, untested) | MotionDriver using the existing jump animations | Sprint + jump at a gap: he lands *exactly* on the highlighted edge, every time. |
| **P2 — AC1 jump animations** (built, untested) | Clip pack + PosePlayer: takeoff / flight / reception chosen and blended like AC1 | The real AC1 free-run jumps, including the "front 3 m", "down 5.5 m" and roof-to-roof receptions. |
| **P3 — Ledges** | Catch-to-hang, hang, shimmy, pull-up, drop | Jump at a wall too high to land on: he catches it and hangs. |
| **P4 — Beams, poles, wall run** | Narrow-object context, walling | Beam runs, pole hops, wall run up to a ledge. |
| **P5 — Polish** | Settings page (button chord, assist strength, overlay), per-city baked edges, sound cues | Ship it. |

## 5. Risks and how we handle them

- **Edge detection noise** (furniture, banners, uneven rooftops). Use a collision filter limited to static and
  terrain layers, minimum edge length (0.5 m), merge colinear pieces, and smooth normals. The P0 overlay lets us
  see mistakes before anything moves.
- **Skyrim's character controller fighting the driver.** Drive velocity rather than position, and switch the
  controller to its "jumping / in-air" state while a free-run jump runs. Faith Runner and FreeClimb both prove
  this works.
- **Pose-writing conflicts with OAR, SkyParkour and FreeClimb.** Only write poses while our state is active,
  never during their moves. Our free-run trigger (sprint + jump with a target) is distinct from SkyParkour's
  vault (jump at a low obstacle), and we yield when SkyParkour is mid-move.
- **Build.** CommonLibSSE-NG and vcpkg already build on this PC (faith-runner's `skyrim/build`). The new plugin
  gets its **own** folder and build directory and only *reads* those sources.
