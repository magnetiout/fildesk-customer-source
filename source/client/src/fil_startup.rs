//! Opt-in, numeric-only timing evidence. Not security/authorization state.
use std::sync::{Mutex,OnceLock};
static EVENTS:OnceLock<Mutex<Vec<(u32,u64)>>>=OnceLock::new();
#[no_mangle]
pub extern "C" fn fil_startup_phase(phase:u32) {
 if std::env::var("FIL_STARTUP_TIMING").as_deref()!=Ok("1") || !(1..=10).contains(&phase) {return}
 #[cfg(windows)]
 let now=unsafe{windows::Win32::System::SystemInformation::GetTickCount64()};
 #[cfg(not(windows))]
 let now=0;
 let origin=std::env::var("FIL_STARTUP_ORIGIN_MS").ok().and_then(|v|v.parse::<u64>().ok()).unwrap_or(now);
 let elapsed=now.saturating_sub(origin);
 if let Ok(mut events)=EVENTS.get_or_init(Default::default).lock() {
  if events.iter().any(|(p,_)|*p==phase) {return}
  events.push((phase,elapsed));
  hbb_common::log::info!("fil_startup phase={} elapsed_ms={}",phase,elapsed);
 }
}
pub fn snapshot()->serde_json::Value {
 let events=EVENTS.get_or_init(Default::default).lock().map(|v|v.clone()).unwrap_or_default();
 serde_json::json!({"enabled":std::env::var("FIL_STARTUP_TIMING").as_deref()==Ok("1"),"events":events})
}
