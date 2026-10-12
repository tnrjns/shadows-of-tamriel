//! Dump Altaïr's skeleton and selected locomotion clips from the user's AC1 install to JSON.
//! The forge / animation / skeleton decoders are compiled straight from the AC1-Movement-Rewritten
//! checkout (read-only, via #[path]); nothing in that project is modified.
//! Usage: ac1_anim_export <game_dir> <out.json> [spec.json]   (spec: {"clip": ["part", ...], ...})
//!        ac1_anim_export <game_dir> --list <substring>
#![allow(dead_code)]

mod assets {
    #[path = "C:/Users/myste/Downloads/AC1-Movement-Rewritten/src/assets/forge.rs"]
    pub mod forge;
    #[path = "C:/Users/myste/Downloads/AC1-Movement-Rewritten/src/assets/ac_anim.rs"]
    pub mod ac_anim;
    #[path = "C:/Users/myste/Downloads/AC1-Movement-Rewritten/src/assets/ac_actions.rs"]
    pub mod ac_actions;
    #[path = "C:/Users/myste/Downloads/AC1-Movement-Rewritten/src/assets/dare.rs"]
    pub mod dare;
}
mod skeleton;
use assets::{ac_anim, forge};
use skeleton as ac_formats;
use std::collections::BTreeMap;
use std::fmt::Write;
use std::path::Path;

/// Same clip names / joined halves as AC1-Movement-Rewritten src/assets/anims.rs LOCOMOTION.
const CLIPS: &[(&str, &[&str])] = &[
    ("idle_low", &["xx_l_wait_hipm_footl"]),
    ("idle_high", &["xx_h_wait_hipm_footl"]),
    ("walk", &["xx_l_walk_hipm_footl", "xx_l_walk_hipm_footr"]),
    ("jog", &["xx_h_jog_hipm_footl", "xx_h_jog_hipm_footr"]),
    ("run", &["xx_h_run_hipm_footl", "xx_h_run_hipm_footr"]),
    ("sprint", &["xx_h_sprint_hipm_footl", "xx_h_sprint_hipm_footr"]),
    ("jump", &["xx_h_jumpstraight_clear_footl"]),
    ("fall", &["xx_h_jumpfalling01"]),
    ("land_soft", &["xx_h_landing_forward_soft_footl_tr_h_jog_footr_a"]),
    ("land_hard", &["xx_h_landing_damage_footl"]),
    ("roll", &["xx_roll_hipm"]),
];

fn f(v: f32) -> String { format!("{:.6}", v) }
fn arr(v: &[f32]) -> String { format!("[{}]", v.iter().map(|x| f(*x)).collect::<Vec<_>>().join(",")) }

fn main() -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    let game = Path::new(&args[1]);
    let mut forge = forge::Forge::open(&game.join("DataPC.forge")).map_err(|e| e.to_string())?;
    if args[2] == "--graph" {
        // every ActionBlock -> action -> clip names (read-only dump of the game's animation graph)
        let gf = forge.find("Game Fix").cloned().ok_or("Game Fix missing")?;
        let res = forge.resources(&gf).map_err(|e| e.to_string())?;
        let names: std::collections::HashMap<u32, String> = res.iter().filter(|r| r.class_hash == 0x0FA3_067F)
            .map(|r| (r.id, r.name.clone())).collect();
        let mut g = assets::ac_actions::ActionGraph::default();
        for r in res.iter().filter(|r| r.class_hash == assets::ac_actions::CLASS_ACTION_BLOCK) {
            g.add_block(&r.name, &r.payload)?;
        }
        let mut acts: Vec<_> = g.actions.values().collect();
        acts.sort_by(|a, b| (a.block.as_str(), a.id).cmp(&(b.block.as_str(), b.id)));
        for a in acts {
            let clips: Vec<String> = a.items.iter().flat_map(|it| it.animations.iter())
                .map(|id| names.get(id).cloned().unwrap_or(format!("#{id:08x}"))).collect();
            println!("{}	{:08x}	{}", a.block, a.id, clips.join(" "));
        }
        return Ok(());
    }
    if args[2] == "--sounds" {
        // ac1_anim_export <game> --sounds <out_dir> <clip>...: every audio event of the clips -> WAV files
        let bank = assets::dare::load_sound_bank(game)?;
        let out_dir = Path::new(&args[3]);
        std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
        let gf = forge.find("Game Fix").cloned().ok_or("Game Fix missing")?;
        let res = forge.resources(&gf).map_err(|e| e.to_string())?;
        for clip in &args[4..] {
            let r = res.iter().find(|r| r.name == clip.as_str() && r.class_hash == 0x0FA3_067F)
                .ok_or(format!("clip {clip} missing"))?;
            let a = ac_anim::decode(&r.payload).map_err(|e| format!("{clip}: {e}"))?;
            for (ei, ev) in a.events.iter().enumerate() {
                let event = match &ev.kind {
                    ac_anim::EventKind::Audio { sound } => bank.event_for_resource(*sound).or(Some(*sound)),
                    ac_anim::EventKind::Contact { ty, .. } => bank.contact.get(*ty as usize).copied().flatten(),
                    _ => None,
                };
                println!("{clip}	{:.3}	{:?}	event {:08x?}", ev.time, ev.kind, event);
                let Some(event) = event else { continue };
                for seed in 1..=3u32 {
                    let mut pick = assets::dare::Picker::new(seed);
                    for (vi, v) in bank.resolve(event, &|_| None, &mut pick).iter().enumerate() {
                        let Some(pcm) = bank.object(v.res).and_then(|o| assets::dare::decode_ima(o, v.channels, v.frames)) else { continue };
                        let name = out_dir.join(format!("{clip}_{ei}_{:08x}_{vi}.wav", v.res));
                        if name.exists() { continue; }
                        let mut w = Vec::new();
                        let data_len = (pcm.len() * 2) as u32;
                        w.extend_from_slice(b"RIFF"); w.extend_from_slice(&(36 + data_len).to_le_bytes());
                        w.extend_from_slice(b"WAVEfmt "); w.extend_from_slice(&16u32.to_le_bytes());
                        w.extend_from_slice(&1u16.to_le_bytes()); w.extend_from_slice(&v.channels.to_le_bytes());
                        w.extend_from_slice(&v.rate.to_le_bytes());
                        w.extend_from_slice(&(v.rate * 2 * v.channels as u32).to_le_bytes());
                        w.extend_from_slice(&(2 * v.channels).to_le_bytes()); w.extend_from_slice(&16u16.to_le_bytes());
                        w.extend_from_slice(b"data"); w.extend_from_slice(&data_len.to_le_bytes());
                        for s in &pcm { w.extend_from_slice(&s.to_le_bytes()); }
                        std::fs::write(&name, w).map_err(|e| e.to_string())?;
                        println!("  -> {} ({} ch, {} Hz, {:.2}s, {:.1} dB)", name.display(), v.channels, v.rate,
                            v.frames as f32 / v.rate as f32, v.gain_db);
                    }
                }
            }
        }
        return Ok(());
    }
    if args[2] == "--list" {
        let gf = forge.find("Game Fix").cloned().ok_or("Game Fix missing")?;
        let res = forge.resources(&gf).map_err(|e| e.to_string())?;
        let pat = args.get(3).cloned().unwrap_or_default();
        let mut names: Vec<(String, f32)> = res.iter().filter(|r| r.class_hash == 0x0FA3_067F && r.name.contains(&pat))
            .map(|r| (r.name.clone(), ac_anim::decode(&r.payload).map(|a| a.duration).unwrap_or(-1.0))).collect();
        names.sort_by(|a, b| a.0.cmp(&b.0));
        for (n, d) in names { println!("{n}	{d:.3}"); }
        return Ok(());
    }
    let spec: Vec<(String, Vec<String>)> = match args.get(3) {
        Some(p) => parse_spec(&std::fs::read_to_string(p).map_err(|e| e.to_string())?),
        None => CLIPS.iter().map(|(c, ps)| (c.to_string(), ps.iter().map(|s| s.to_string()).collect())).collect(),
    };
    let mut out = String::from("{\n");

    // skeleton
    let rank9 = forge.find("Rank 9").cloned().ok_or("Rank 9 missing")?;
    let res = forge.resources(&rank9).map_err(|e| e.to_string())?;
    let skel = res.iter()
        .find(|r| r.name == "UCMA_Altair" && r.class_hash == forge::crc32("Skeleton"))
        .ok_or("UCMA_Altair skeleton missing")?;
    let bones = ac_formats::parse_skeleton(&skel.payload);
    out += "\"skeleton\": [\n";
    for (i, b) in bones.iter().enumerate() {
        let _ = write!(out, "{{\"bone_id\":\"{:08x}\",\"parent\":{},\"local_pos\":{},\"local_rot\":{},\"global_pos\":{},\"global_rot\":{}}}{}\n",
            b.bone_id, b.parent.map(|p| p as i64).unwrap_or(-1), arr(&b.local_pos), arr(&b.local_rot),
            arr(&b.global_pos), arr(&b.global_rot), if i + 1 < bones.len() { "," } else { "" });
    }
    out += "],\n\"clips\": {\n";

    // clips
    let gf = forge.find("Game Fix").cloned().ok_or("Game Fix missing")?;
    let res = forge.resources(&gf).map_err(|e| e.to_string())?;
    for (ci, (clip, parts)) in spec.iter().enumerate() {
        let mut dur = 0f32;
        let mut rot: BTreeMap<u32, Vec<(f32, [f32; 4])>> = BTreeMap::new();
        let mut pos: BTreeMap<u32, Vec<(f32, [f32; 3])>> = BTreeMap::new();
        let mut disp_end = [0f32; 3];
        let mut contacts: Vec<(f32, u8)> = Vec::new();
        for part in parts.iter() {
            let r = res.iter().find(|r| r.name == part.as_str() && r.class_hash == 0x0FA3_067F)
                .ok_or(format!("clip {part} missing"))?;
            let a = ac_anim::decode(&r.payload).map_err(|e| format!("{part}: {e}"))?;
            let (rk, pk) = ac_anim::bone_tracks(&a);
            for t in &a.tracks {
                if t.key == 2 {
                    if let ac_anim::TrackValues::Byte(v) = &t.values {
                        for (tm, b) in t.times.iter().zip(v.iter()) { contacts.push((tm + dur, *b)); }
                    }
                }
            }
            for (k, keys) in rk { let v = rot.entry(k).or_default(); for (t, q) in keys { v.push((t + dur, q)); } }
            let mut last_disp = disp_end;
            for (k, keys) in pk {
                let base = if k == ac_anim::TRACK_DISPLACEMENT { disp_end } else { [0.0; 3] };
                let v = pos.entry(k).or_default();
                for (t, p) in keys {
                    let q = [p[0] + base[0], p[1] + base[1], p[2] + base[2]];
                    if k == ac_anim::TRACK_DISPLACEMENT { last_disp = q; }
                    v.push((t + dur, q));
                }
            }
            disp_end = last_disp;
            dur += a.duration;
        }
        let _ = write!(out, "\"{clip}\": {{\"duration\":{},\"parts\":{:?},\"rot\":{{", f(dur), parts);
        let rs: Vec<String> = rot.iter().map(|(k, v)| format!("\"{:08x}\":[{}]", k,
            v.iter().map(|(t, q)| format!("[{},{},{},{},{}]", f(*t), f(q[0]), f(q[1]), f(q[2]), f(q[3]))).collect::<Vec<_>>().join(","))).collect();
        out += &rs.join(",");
        out += "},\"pos\":{";
        let ps: Vec<String> = pos.iter().map(|(k, v)| format!("\"{:08x}\":[{}]", k,
            v.iter().map(|(t, p)| format!("[{},{},{},{}]", f(*t), f(p[0]), f(p[1]), f(p[2]))).collect::<Vec<_>>().join(","))).collect();
        out += &ps.join(",");
        let cs: Vec<String> = contacts.iter().map(|(t, b)| format!("[{},{}]", f(*t), b)).collect();
        let _ = write!(out, "}},\"contacts\":[{}]}}{}\n", cs.join(","), if ci + 1 < spec.len() { "," } else { "" });
        eprintln!("{clip}: {:.3}s, {} rot tracks, {} pos tracks", dur, rot.len(), pos.len());
    }
    out += "}\n}\n";
    std::fs::write(&args[2], out).map_err(|e| e.to_string())?;
    eprintln!("skeleton bones: {}", bones.len());
    Ok(())
}

/// Minimal parser for {"clip": ["part", ...], ...} (no escapes needed for these names).
fn parse_spec(t: &str) -> Vec<(String, Vec<String>)> {
    let mut out = Vec::new();
    let mut strs = Vec::new();
    let mut depth = 0;
    let mut cur: Option<String> = None;
    let mut key: Option<String> = None;
    for ch in t.chars() {
        match (ch, cur.is_some()) {
            ('"', false) => cur = Some(String::new()),
            ('"', true) => {
                let s = cur.take().unwrap();
                if depth == 1 { key = Some(s); } else { strs.push(s); }
            }
            (c, true) => cur.as_mut().unwrap().push(c),
            ('{', _) | ('[', _) => depth += 1,
            (']', _) => { depth -= 1; if let Some(k) = key.take() { out.push((k, std::mem::take(&mut strs))); } }
            ('}', _) => depth -= 1,
            _ => {}
        }
    }
    out
}
