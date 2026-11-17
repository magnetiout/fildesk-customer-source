//! Explicit local opt-in measurements. Never writes a log file, payload, path or identity.
use std::{ffi::OsStr, io::Write, time::Instant};

#[derive(Clone, Copy)]
pub(crate) enum Phase {
    LauncherEntered, InventoryReady, InventoryRejected, PrivateDirectoryReady,
    ExtractionVerified, ExtractionRejected, InnerProcessCreated, PortableTreeExited, CleanupComplete,
}
impl Phase {
    fn label(self) -> &'static str {
        match self {
            Self::LauncherEntered => "launcher_entered", Self::InventoryReady => "inventory_ready",
            Self::InventoryRejected => "inventory_rejected", Self::PrivateDirectoryReady => "private_directory_ready",
            Self::ExtractionVerified => "extraction_verified", Self::ExtractionRejected => "extraction_rejected",
            Self::InnerProcessCreated => "inner_process_created", Self::PortableTreeExited => "portable_tree_exited",
            Self::CleanupComplete => "cleanup_complete",
        }
    }
}
fn opted_in(value: Option<&OsStr>) -> bool { value == Some(OsStr::new("1")) }
fn micros(start: Instant) -> u64 { start.elapsed().as_micros().min(u64::MAX as u128) as u64 }

pub(crate) struct StartupTiming { enabled: bool, start: Instant }
#[derive(Default)]
pub(crate) struct ExtractionTimings {
    pub decode_us: u64, pub directories_us: u64, pub write_us: u64,
    pub flush_us: u64, pub readback_us: u64, pub signature_us: u64,
}
impl StartupTiming {
    pub fn new() -> Self { Self { enabled: opted_in(std::env::var_os("FIL_STARTUP_TIMING").as_deref()), start: Instant::now() } }
    #[cfg(test)]
    pub fn disabled() -> Self { Self { enabled: false, start: Instant::now() } }
    pub fn span(&self) -> Option<Instant> { self.enabled.then(Instant::now) }
    pub fn add_elapsed(total: &mut u64, span: Option<Instant>) {
        if let Some(start) = span { *total = total.saturating_add(micros(start)); }
    }
    fn line(phase: Phase, elapsed_us: u64, files: usize, bytes: u64) -> String {
        format!("{{\"schema\":1,\"component\":\"portable\",\"phase\":\"{}\",\"elapsed_us\":{elapsed_us},\"files\":{files},\"bytes\":{bytes}}}", phase.label())
    }
    pub fn mark(&self, phase: Phase, files: usize, bytes: u64) {
        if self.enabled { let _ = writeln!(std::io::stderr().lock(), "{}", Self::line(phase, micros(self.start), files, bytes)); }
    }
    pub fn extraction(&self, value: &ExtractionTimings, files: usize, bytes: u64) {
        if self.enabled {
            let _ = writeln!(std::io::stderr().lock(), "{{\"schema\":1,\"component\":\"portable\",\"phase\":\"extraction_profile\",\"elapsed_us\":{},\"files\":{files},\"bytes\":{bytes},\"decode_us\":{},\"directories_us\":{},\"write_us\":{},\"flush_us\":{},\"readback_us\":{},\"signature_us\":{}}}", micros(self.start), value.decode_us, value.directories_us, value.write_us, value.flush_us, value.readback_us, value.signature_us);
        }
    }
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn requires_exact_opt_in() { for v in [None, Some(OsStr::new("")), Some(OsStr::new("0")), Some(OsStr::new("true"))] { assert!(!opted_in(v)); } assert!(opted_in(Some(OsStr::new("1")))); }
    #[test] fn disabled_does_not_collect_spans() { let timer=StartupTiming::disabled(); assert!(timer.span().is_none()); let mut value=7; StartupTiming::add_elapsed(&mut value,None); assert_eq!(value,7); }
    #[test] fn output_contains_only_static_phase_and_numeric_fields() { assert_eq!(StartupTiming::line(Phase::InventoryReady,12,97,56),"{\"schema\":1,\"component\":\"portable\",\"phase\":\"inventory_ready\",\"elapsed_us\":12,\"files\":97,\"bytes\":56}"); }
}
