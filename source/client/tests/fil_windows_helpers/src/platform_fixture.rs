//! Only parent integration boundaries are unavailable here. Production module
//! uses real Windows bindings. A bridge call would fail this isolated test.
use std::io;
use windows::Win32::Foundation::HANDLE;

fn is_elevated(_: Option<u32>) -> io::Result<bool> {
    panic!("Customer rejection must occur before elevation APIs");
}
fn get_current_process_session_id() -> Option<u32> {
    panic!("Privileged bridge must not run in isolated helper tests");
}
unsafe fn read_token_user_buffer(_: HANDLE, _: &str) -> io::Result<Vec<u8>> {
    panic!("Privileged bridge must not run in isolated helper tests");
}
#[allow(non_snake_case)]
unsafe fn GetSessionUserTokenWin(
    _: *mut winapi::um::winnt::HANDLE,
    _: u32,
    _: i32,
    _: &mut u32,
) -> i32 {
    panic!("Privileged bridge must not run in isolated helper tests");
}

#[path = "../../../src/platform/windows/system_launcher.rs"]
mod system_launcher;

#[test]
fn operator_or_unscoped_helper_is_rejected_before_any_native_elevation_or_token_operation() {
    let error = system_launcher::launch("--run-as-system").unwrap_err();
    assert_eq!(error.kind(), io::ErrorKind::PermissionDenied);
}
