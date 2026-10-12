//! Copy of `parse_skeleton` from AC1-Movement-Rewritten src/assets/ac_formats.rs (that file also
//! needs Bevy, so it can't be included directly). Transforms: skeleton space, Z-up, metres.
fn u32_at(b: &[u8], o: usize) -> Option<u32> {
    b.get(o..o + 4).map(|s| u32::from_le_bytes(s.try_into().unwrap()))
}
fn f32_at(b: &[u8], o: usize) -> f32 {
    f32::from_le_bytes(b[o..o + 4].try_into().unwrap())
}
pub struct SkelBone {
    pub object_id: u32,
    pub bone_id: u32,
    pub parent: Option<usize>,
    pub local_pos: [f32; 3],
    pub local_rot: [f32; 4],
    pub global_pos: [f32; 3],
    pub global_rot: [f32; 4],
}
pub const CLASS_BONE: u32 = 0x9574_1049;
pub fn parse_skeleton(d: &[u8]) -> Vec<SkelBone> {
    let mut bones: Vec<SkelBone> = Vec::new();
    let mut parents: Vec<Option<u32>> = Vec::new();
    let mut i = 8;
    while i + 9 < d.len() {
        if d[i] == 0 && u32_at(d, i + 5) == Some(CLASS_BONE) {
            let mut p = i + 9;
            let object_id = u32_at(d, i + 1).unwrap();
            let bone_id = u32_at(d, p).unwrap();
            p += 4;
            let parent = if d[p] == 2 { p += 5; u32_at(d, p - 4) } else { p += 1; None };
            p += 9;
            let f = |o: usize| f32_at(d, o);
            bones.push(SkelBone {
                object_id, bone_id, parent: None,
                global_pos: [f(p), f(p + 4), f(p + 8)],
                global_rot: [f(p + 16), f(p + 20), f(p + 24), f(p + 28)],
                local_pos: [f(p + 32), f(p + 36), f(p + 40)],
                local_rot: [f(p + 48), f(p + 52), f(p + 56), f(p + 60)],
            });
            parents.push(parent);
            i = p + 64;
        } else {
            i += 1;
        }
    }
    for k in 0..bones.len() {
        if let Some(pid) = parents[k] {
            bones[k].parent = bones.iter().position(|b| b.object_id == pid);
        }
    }
    bones
}
