// SPDX-License-Identifier: AGPL-3.0-only
//! Supported local UAC request only; caller still waits for authenticated helper IPC.
use std::io;
fn declined_or_error(code:u32)->io::Result<bool> {
    if code==1223 { Ok(false) }
    else if code==0 { Err(io::Error::other("Windows did not start the UAC helper")) }
    else { Err(io::Error::from_raw_os_error(code as i32)) }
}
#[cfg(windows)]
pub(super) fn launch(executable:&str,arguments:&str)->io::Result<bool> {
    use std::mem;
    use winapi::um::{shellapi::{ShellExecuteExW,SHELLEXECUTEINFOW,SEE_MASK_NOCLOSEPROCESS,SEE_MASK_NOASYNC},errhandlingapi::GetLastError,handleapi::CloseHandle,winuser::SW_SHOWNORMAL};
    if executable.contains('\0') || arguments.contains('\0') {return Err(io::Error::new(io::ErrorKind::InvalidInput,"Invalid UAC request"))}
    // ShellExecuteEx may activate COM shell handlers. This request owns its worker apartment.
    unsafe { windows::Win32::System::Com::CoInitializeEx(None, windows::Win32::System::Com::COINIT_APARTMENTTHREADED | windows::Win32::System::Com::COINIT_DISABLE_OLE1DDE) }.ok().map_err(io::Error::other)?;
    struct Apartment;
    impl Drop for Apartment { fn drop(&mut self) { unsafe { windows::Win32::System::Com::CoUninitialize(); } } }
    let _apartment=Apartment;
    let verb:Vec<u16>="runas".encode_utf16().chain(Some(0)).collect();
    let exe:Vec<u16>=executable.encode_utf16().chain(Some(0)).collect();
    let args:Vec<u16>=arguments.encode_utf16().chain(Some(0)).collect();
    unsafe {
        let mut info:SHELLEXECUTEINFOW=mem::zeroed();
        info.cbSize=mem::size_of::<SHELLEXECUTEINFOW>() as u32;
        info.fMask=SEE_MASK_NOCLOSEPROCESS|SEE_MASK_NOASYNC;
        info.lpVerb=verb.as_ptr();info.lpFile=exe.as_ptr();info.lpParameters=args.as_ptr();
        info.nShow=SW_SHOWNORMAL;
        if ShellExecuteExW(&mut info)==0 {return declined_or_error(GetLastError())}
        if !info.hProcess.is_null() && CloseHandle(info.hProcess)==0 {return Err(io::Error::last_os_error())}
        Ok(true)
    }
}
#[cfg(test)]mod tests {
 use super::*;
 #[test]fn cancellation_is_not_a_missing_file_or_policy_failure(){assert_eq!(declined_or_error(1223).unwrap(),false);for code in [0,2,5,740]{assert!(declined_or_error(code).is_err());}}
 #[test]fn native_error_code_is_retained_without_path_or_credentials(){assert_eq!(declined_or_error(5).unwrap_err().raw_os_error(),Some(5));}
}
