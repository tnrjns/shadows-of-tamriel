//! AltairAC1Menu.dll - the "Altair AC1" page in SKSE Menu Framework (Mod Control Panel).
//!
//! No CommonLib: the plugin only talks to SKSE's loader interface and to SKSE Menu Framework's exported C functions
//! (cimgui-style `ig*` ImGui calls and `AddSectionItem`), so it does not touch game memory and is version independent.
//! Settings are written as `key=value` lines to Data/SKSE/Plugins/AltairAC1Settings.ini; the AltairAC1Settings quest
//! (AltairLeapOfFaith.esp) reads that file every second and applies it in game. Buttons bump a counter in the file.
#![allow(non_snake_case, clippy::missing_safety_doc)]

use std::ffi::{c_char, c_void, CStr};
use std::sync::Mutex;

const SETTINGS_DIR: &str = "Data/SKSE/Plugins";
const SETTINGS_FILE: &str = "Data/SKSE/Plugins/AltairAC1Settings.ini";

// ------------------------------------------------------------------------------------------------ settings
#[derive(Clone, PartialEq)]
struct Settings {
    leap_enabled: bool,
    leap_guidance: f32,
    leap_arm_height: f32, // metres
    leap_arm_radius: f32,
    leap_safe_radius: f32,
    leap_ready_message: bool,
    leap_volume: f32,
    anim_locomotion: bool,
    anim_parkour: bool,
    anim_leap_dive: bool,
    debug: bool,
    cmd_power: i32,
    cmd_hay_here: i32,
    cmd_goto_solitude: i32,
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            leap_enabled: true,
            leap_guidance: 0.6,
            leap_arm_height: 8.0,
            leap_arm_radius: 15.0,
            leap_safe_radius: 7.5,
            leap_ready_message: true,
            leap_volume: 1.0,
            anim_locomotion: true,
            anim_parkour: true,
            anim_leap_dive: true,
            debug: false,
            cmd_power: 0,
            cmd_hay_here: 0,
            cmd_goto_solitude: 0,
        }
    }
}

impl Settings {
    fn load() -> Settings {
        let mut s = Settings::default();
        let Ok(text) = std::fs::read_to_string(SETTINGS_FILE) else { return s };
        for line in text.lines() {
            let Some((k, v)) = line.split_once('=') else { continue };
            let (k, v) = (k.trim(), v.trim());
            let f = v.parse::<f32>().unwrap_or(0.0);
            let b = f != 0.0;
            match k {
                "leap_enabled" => s.leap_enabled = b,
                "leap_guidance" => s.leap_guidance = f,
                "leap_arm_height" => s.leap_arm_height = f,
                "leap_arm_radius" => s.leap_arm_radius = f,
                "leap_safe_radius" => s.leap_safe_radius = f,
                "leap_ready_message" => s.leap_ready_message = b,
                "leap_volume" => s.leap_volume = f,
                "anim_locomotion" => s.anim_locomotion = b,
                "anim_parkour" => s.anim_parkour = b,
                "anim_leap_dive" => s.anim_leap_dive = b,
                "debug" => s.debug = b,
                "cmd_power" => s.cmd_power = f as i32,
                "cmd_hay_here" => s.cmd_hay_here = f as i32,
                "cmd_goto_solitude" => s.cmd_goto_solitude = f as i32,
                _ => {}
            }
        }
        s
    }

    fn save(&self) {
        let b = |v: bool| if v { 1 } else { 0 };
        let text = format!(
            "leap_enabled={}\nleap_guidance={:.2}\nleap_arm_height={:.1}\nleap_arm_radius={:.1}\nleap_safe_radius={:.1}\n\
             leap_ready_message={}\nleap_volume={:.2}\nanim_locomotion={}\nanim_parkour={}\nanim_leap_dive={}\ndebug={}\n\
             cmd_power={}\ncmd_hay_here={}\ncmd_goto_solitude={}\n",
            b(self.leap_enabled), self.leap_guidance, self.leap_arm_height, self.leap_arm_radius, self.leap_safe_radius,
            b(self.leap_ready_message), self.leap_volume, b(self.anim_locomotion), b(self.anim_parkour),
            b(self.anim_leap_dive), b(self.debug), self.cmd_power, self.cmd_hay_here, self.cmd_goto_solitude
        );
        let _ = std::fs::create_dir_all(SETTINGS_DIR);
        let _ = std::fs::write(SETTINGS_FILE, text);
    }
}

static SETTINGS: Mutex<Option<Settings>> = Mutex::new(None);

// ------------------------------------------------------------------------------------------------ win32 / framework
#[link(name = "kernel32")]
extern "system" {
    fn GetModuleHandleA(name: *const c_char) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const c_char) -> *mut c_void;
}

#[repr(C)]
#[derive(Clone, Copy)]
struct ImVec2 {
    x: f32,
    y: f32,
}

type RenderFn = unsafe extern "system" fn();

struct Gui {
    add_section_item: unsafe extern "C" fn(*const c_char, RenderFn),
    text_unformatted: unsafe extern "C" fn(*const c_char, *const c_char),
    separator_text: unsafe extern "C" fn(*const c_char),
    checkbox: unsafe extern "C" fn(*const c_char, *mut bool) -> bool,
    slider_float: unsafe extern "C" fn(*const c_char, *mut f32, f32, f32, *const c_char, i32) -> bool,
    button: unsafe extern "C" fn(*const c_char, ImVec2) -> bool,
    same_line: unsafe extern "C" fn(f32, f32),
    spacing: unsafe extern "C" fn(),
    is_item_hovered: unsafe extern "C" fn(i32) -> bool,
    begin_tooltip: unsafe extern "C" fn() -> bool,
    end_tooltip: unsafe extern "C" fn(),
}

static GUI: Mutex<Option<Gui>> = Mutex::new(None);

unsafe fn proc<T: Copy>(module: *mut c_void, name: &CStr) -> Option<T> {
    let p = GetProcAddress(module, name.as_ptr());
    if p.is_null() {
        None
    } else {
        Some(std::mem::transmute_copy::<*mut c_void, T>(&p))
    }
}

unsafe fn resolve() -> Option<Gui> {
    let m = GetModuleHandleA(c"SKSEMenuFramework".as_ptr());
    if m.is_null() {
        return None;
    }
    Some(Gui {
        add_section_item: proc(m, c"AddSectionItem")?,
        text_unformatted: proc(m, c"igTextUnformatted")?,
        separator_text: proc(m, c"igSeparatorText")?,
        checkbox: proc(m, c"igCheckbox")?,
        slider_float: proc(m, c"igSliderFloat")?,
        button: proc(m, c"igButton")?,
        same_line: proc(m, c"igSameLine")?,
        spacing: proc(m, c"igSpacing")?,
        is_item_hovered: proc(m, c"igIsItemHovered")?,
        begin_tooltip: proc(m, c"igBeginTooltip")?,
        end_tooltip: proc(m, c"igEndTooltip")?,
    })
}

// small helpers over the C API (strings are NUL-terminated literals)
fn z(s: &str) -> Vec<u8> {
    let mut v = s.as_bytes().to_vec();
    v.push(0);
    v
}

impl Gui {
    unsafe fn text(&self, s: &str) {
        let b = z(s);
        (self.text_unformatted)(b.as_ptr().cast(), std::ptr::null());
    }
    unsafe fn tip(&self, s: &str) {
        if (self.is_item_hovered)(0) && (self.begin_tooltip)() {
            self.text(s);
            (self.end_tooltip)();
        }
    }
    unsafe fn header(&self, s: &str) {
        (self.spacing)();
        let b = z(s);
        (self.separator_text)(b.as_ptr().cast());
    }
    unsafe fn check(&self, label: &str, v: &mut bool, tip: &str) -> bool {
        let b = z(label);
        let r = (self.checkbox)(b.as_ptr().cast(), v);
        self.tip(tip);
        r
    }
    unsafe fn slider(&self, label: &str, v: &mut f32, lo: f32, hi: f32, fmt: &str, tip: &str) -> bool {
        let (b, f) = (z(label), z(fmt));
        let r = (self.slider_float)(b.as_ptr().cast(), v, lo, hi, f.as_ptr().cast(), 0x10); // AlwaysClamp
        self.tip(tip);
        r
    }
    unsafe fn button(&self, label: &str, tip: &str) -> bool {
        let b = z(label);
        let r = (self.button)(b.as_ptr().cast(), ImVec2 { x: 0.0, y: 0.0 });
        self.tip(tip);
        r
    }
}

// ------------------------------------------------------------------------------------------------ the page
unsafe extern "system" fn render() {
    let gui_lock = GUI.lock().unwrap_or_else(|e| e.into_inner());
    let Some(gui) = gui_lock.as_ref() else { return };
    let mut lock = SETTINGS.lock().unwrap_or_else(|e| e.into_inner());
    let s = lock.get_or_insert_with(Settings::load);
    let before = s.clone();

    gui.text("Assassin's Creed 1 movement for Skyrim. Changes apply in game within a second.");

    gui.header("Leap of Faith");
    gui.check("Enable leaps of faith", &mut s.leap_enabled,
        "Stand high above a haystack and jump to take a leap of faith.");
    gui.slider("Pull toward the hay", &mut s.leap_guidance, 0.0, 1.0, "%.2f",
        "How strongly the dive is steered into the haystack.\n0 = no help (pure physics), 1 = straight into the hay from up to 21 m away.");
    gui.slider("Minimum height (m)", &mut s.leap_arm_height, 3.0, 40.0, "%.1f m",
        "How far above the haystack you must stand for the leap to arm.");
    gui.slider("Reach (m)", &mut s.leap_arm_radius, 3.0, 40.0, "%.1f m",
        "How far to the side of the haystack you can be and still leap into it.");
    gui.slider("Safe landing radius (m)", &mut s.leap_safe_radius, 2.0, 20.0, "%.1f m",
        "Within this distance of the haystack the fall does no damage.");
    gui.check("Show \"Leap of Faith ready\"", &mut s.leap_ready_message,
        "Show a message when you are in position to leap.");
    gui.slider("Leap sound volume", &mut s.leap_volume, 0.0, 1.0, "%.2f",
        "Volume of the AC1 eagle cry / wind and the haystack landing.");
    if gui.button("Give me Place Haystack", "Adds the Place Haystack power, if you don't have it.") {
        s.cmd_power += 1;
    }
    (gui.same_line)(0.0, -1.0);
    if gui.button("Haystack in front of me", "Moves the portable haystack a few steps in front of you.") {
        s.cmd_hay_here += 1;
    }
    (gui.same_line)(0.0, -1.0);
    if gui.button("Go to the Solitude haystack", "Teleports you onto the haystack below the Solitude windmill bridge.") {
        s.cmd_goto_solitude += 1;
    }

    gui.header("Animations (on you)");
    gui.check("AC1 locomotion", &mut s.anim_locomotion,
        "Idle, walk/run/sprint, turning, jumps, sneaking, roll and sword combat from AC1.");
    gui.check("AC1 parkour (SkyParkour)", &mut s.anim_parkour,
        "AC1 vault / climb / land-roll animations for SkyParkour.");
    gui.check("AC1 leap-of-faith dive", &mut s.anim_leap_dive,
        "The swan dive and haystack landing. Off = the leap still works, with your normal jump animations.");

    gui.header("Advanced");
    gui.check("Debug messages", &mut s.debug, "On-screen messages that show what the scripts are doing.");
    if gui.button("Reset to defaults", "Restore every setting above to its default.") {
        let keep = (s.cmd_power, s.cmd_hay_here, s.cmd_goto_solitude);
        *s = Settings { cmd_power: keep.0, cmd_hay_here: keep.1, cmd_goto_solitude: keep.2, ..Settings::default() };
    }

    if *s != before {
        s.save();
    }
}

// ------------------------------------------------------------------------------------------------ SKSE entry
#[repr(C)]
pub struct SKSEPluginVersionData {
    data_version: u32,
    plugin_version: u32,
    name: [u8; 256],
    author: [u8; 256],
    support_email: [u8; 252],
    version_independence_ex: u32,
    version_independence: u32,
    compatible_versions: [u32; 16],
    se_version_required: u32,
}

const fn fixed<const N: usize>(s: &str) -> [u8; N] {
    let b = s.as_bytes();
    let mut out = [0u8; N];
    let mut i = 0;
    while i < b.len() && i < N - 1 {
        out[i] = b[i];
        i += 1;
    }
    out
}

#[no_mangle]
pub static SKSEPlugin_Version: SKSEPluginVersionData = SKSEPluginVersionData {
    data_version: 1,
    plugin_version: 1,
    name: fixed("AltairAC1Menu"),
    author: fixed("Altair AC1 Skyrim"),
    support_email: fixed(""),
    version_independence_ex: 1,      // kVersionIndependentEx_NoStructUse
    version_independence: 1 | 2 | 4, // address library, signatures, structs post-629: uses no game addresses at all
    compatible_versions: [0; 16],
    se_version_required: 0,
};

#[repr(C)]
pub struct SKSEInterface {
    skse_version: u32,
    runtime_version: u32,
    editor_version: u32,
    is_editor: u32,
    query_interface: unsafe extern "C" fn(u32) -> *mut c_void,
    get_plugin_handle: unsafe extern "C" fn() -> u32,
}

#[repr(C)]
struct SKSEMessagingInterface {
    interface_version: u32,
    register_listener: unsafe extern "C" fn(u32, *const c_char, unsafe extern "C" fn(*mut SKSEMessage)) -> bool,
}

#[repr(C)]
struct SKSEMessage {
    sender: *const c_char,
    msg_type: u32,
    data_len: u32,
    data: *mut c_void,
}

unsafe fn register_page() -> bool {
    let mut g = GUI.lock().unwrap_or_else(|e| e.into_inner());
    if g.is_some() {
        return true;
    }
    let Some(gui) = resolve() else { return false };
    (gui.add_section_item)(c"Altair AC1/Settings".as_ptr(), render);
    *g = Some(gui);
    true
}

unsafe extern "C" fn on_message(msg: *mut SKSEMessage) {
    // kMessage_PostLoad (0) / kMessage_PostPostLoad (1): every plugin, the menu framework included, is loaded
    if !msg.is_null() && (*msg).msg_type <= 1 {
        register_page();
    }
}

#[no_mangle]
pub unsafe extern "C" fn SKSEPlugin_Load(skse: *const SKSEInterface) -> bool {
    if register_page() || skse.is_null() {
        return true;
    }
    let messaging = ((*skse).query_interface)(5) as *const SKSEMessagingInterface; // kInterface_Messaging
    if !messaging.is_null() {
        let handle = ((*skse).get_plugin_handle)();
        ((*messaging).register_listener)(handle, c"SKSE".as_ptr(), on_message);
    }
    true
}
