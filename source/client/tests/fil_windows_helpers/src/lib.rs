//! Actual implementation-source tests; no owner profile or privileged helper is started.
#[cfg(not(windows))]
#[path = "../../../src/platform/windows/system_launcher_args.rs"]
mod helper_args;
#[path = "../../../libs/hbb_common/src/fingerprint_mac.rs"]
#[allow(dead_code)]
mod mac;

#[cfg(windows)]
mod fil_build_config {
    pub const PROFILE: &str = "operator";
}
#[cfg(windows)]
mod platform_fixture;

#[path = "../../../src/platform/windows/portable_uac.rs"]
mod portable_uac;
