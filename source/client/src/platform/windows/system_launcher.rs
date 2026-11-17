// SPDX-License-Identifier: AGPL-3.0-only
// Uses documented Windows token/process APIs and the project's existing
// session-token bridge; no implementation from impersonate-system is included.
use std::{
    io,
    mem::{size_of, zeroed},
    os::windows::ffi::OsStrExt,
    ptr,
    sync::Mutex,
};
use windows::{
    core::{PCWSTR, PWSTR},
    Win32::{
        Foundation::{
            CloseHandle, GetLastError, SetLastError, ERROR_NOT_ALL_ASSIGNED, ERROR_SUCCESS, HANDLE,
            LUID,
        },
        Security::{
            AdjustTokenPrivileges, DuplicateTokenEx, GetTokenInformation, IsWellKnownSid,
            LookupPrivilegeValueW, SecurityImpersonation, TokenPrimary, TokenSessionId,
            WinLocalSystemSid, LUID_AND_ATTRIBUTES, SE_DEBUG_NAME, SE_IMPERSONATE_NAME,
            SE_PRIVILEGE_ENABLED, TOKEN_ADJUST_PRIVILEGES, TOKEN_ASSIGN_PRIMARY, TOKEN_DUPLICATE,
            TOKEN_PRIVILEGES, TOKEN_QUERY, TOKEN_USER,
        },
        System::Threading::{
            CreateProcessWithTokenW, GetCurrentProcess, OpenProcessToken, ResumeThread,
            TerminateProcess, CREATE_SUSPENDED, LOGON_WITH_PROFILE, PROCESS_INFORMATION,
            STARTUPINFOW,
        },
    },
};

#[path = "system_launcher_args.rs"]
mod args;
static PRIVILEGE_SCOPE: Mutex<()> = Mutex::new(());

fn failure(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::PermissionDenied, message)
}
fn os_error(error: windows::core::Error) -> io::Error {
    io::Error::other(error)
}

struct OwnedHandle(HANDLE);
impl Drop for OwnedHandle {
    fn drop(&mut self) {
        if !self.0.is_invalid() {
            if let Err(error) = unsafe { CloseHandle(self.0) } {
                eprintln!("FilDesk helper handle cleanup failed: {}", error.code());
            }
        }
    }
}

struct Privilege<'a> {
    token: &'a OwnedHandle,
    previous: TOKEN_PRIVILEGES,
    active: bool,
}
impl<'a> Privilege<'a> {
    fn enable(token: &'a OwnedHandle, name: PCWSTR) -> io::Result<Self> {
        let mut luid = LUID::default();
        unsafe { LookupPrivilegeValueW(PCWSTR::null(), name, &mut luid) }.map_err(os_error)?;
        let requested = TOKEN_PRIVILEGES {
            PrivilegeCount: 1,
            Privileges: [LUID_AND_ATTRIBUTES {
                Luid: luid,
                Attributes: SE_PRIVILEGE_ENABLED,
            }],
        };
        let mut scope = Self {
            token,
            previous: TOKEN_PRIVILEGES::default(),
            active: false,
        };
        let mut length = 0;
        unsafe {
            SetLastError(ERROR_SUCCESS);
            AdjustTokenPrivileges(
                token.0,
                false,
                Some(&requested),
                size_of::<TOKEN_PRIVILEGES>() as u32,
                Some(&mut scope.previous),
                Some(&mut length),
            )
        }
        .map_err(os_error)?;
        scope.active = true;
        if unsafe { GetLastError() } == ERROR_NOT_ALL_ASSIGNED {
            return Err(failure("Required Windows privilege is not granted"));
        }
        Ok(scope)
    }
    fn restore(&mut self) -> io::Result<()> {
        if self.active {
            unsafe {
                SetLastError(ERROR_SUCCESS);
                AdjustTokenPrivileges(self.token.0, false, Some(&self.previous), 0, None, None)
            }
            .map_err(os_error)?;
            if unsafe { GetLastError() } == ERROR_NOT_ALL_ASSIGNED {
                return Err(failure("Unable to restore Windows privilege state"));
            }
            self.active = false;
        }
        Ok(())
    }
}
impl Drop for Privilege<'_> {
    fn drop(&mut self) {
        if self.restore().is_err() {
            eprintln!("FilDesk helper privilege cleanup failed");
        }
    }
}

fn require_system_session(token: HANDLE, session: u32) -> io::Result<()> {
    let buffer = unsafe { super::read_token_user_buffer(token, "portable helper") }
        .map_err(|_| failure("Unable to verify portable helper identity"))?;
    let user = unsafe { ptr::read_unaligned(buffer.as_ptr() as *const TOKEN_USER) };
    if !unsafe { IsWellKnownSid(user.User.Sid, WinLocalSystemSid) }.as_bool() {
        return Err(failure("Portable helper token is not LocalSystem"));
    }
    let mut token_session = 0u32;
    let mut length = 0;
    unsafe {
        GetTokenInformation(
            token,
            TokenSessionId,
            Some((&mut token_session as *mut u32).cast()),
            size_of::<u32>() as u32,
            &mut length,
        )
    }
    .map_err(os_error)?;
    if length != size_of::<u32>() as u32 || token_session != session {
        return Err(failure(
            "Portable helper token belongs to another Windows session",
        ));
    }
    Ok(())
}

struct Child {
    process: OwnedHandle,
    thread: OwnedHandle,
    started: bool,
}
impl Drop for Child {
    fn drop(&mut self) {
        if !self.started && !self.process.0.is_invalid() {
            if let Err(error) = unsafe { TerminateProcess(self.process.0, 1) } {
                eprintln!("FilDesk suspended helper cleanup failed: {}", error.code());
            }
        }
    }
}

pub(super) fn launch(arguments: &str) -> io::Result<()> {
    if !args::permitted(crate::fil_build_config::PROFILE, arguments) {
        return Err(failure("Only a Customer portable request with scoped IPC may start this helper"));
    }
    if !super::is_elevated(None).map_err(|_| failure("Cannot verify Windows elevation"))? {
        return Err(failure("Explicit Windows elevation is required"));
    }
    let session = super::get_current_process_session_id()
        .ok_or_else(|| failure("Cannot verify current Windows session"))?;
    let executable = std::env::current_exe()?;
    let mut application: Vec<u16> = executable.as_os_str().encode_wide().collect();
    let mut command = args::command(&application, arguments)?;
    application.push(0);
    // Only this helper changes these process-token privileges. Serialize scopes
    // so concurrent starts cannot restore another start's temporary state.
    let _serial = PRIVILEGE_SCOPE
        .lock()
        .map_err(|_| failure("Privilege scope unavailable"))?;
    let mut raw_process_token = HANDLE::default();
    unsafe {
        OpenProcessToken(
            GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            &mut raw_process_token,
        )
    }
    .map_err(os_error)?;
    let process_token = OwnedHandle(raw_process_token);
    let mut debug = Privilege::enable(&process_token, SE_DEBUG_NAME)?;
    let mut impersonate = Privilege::enable(&process_token, SE_IMPERSONATE_NAME)?;
    let mut raw_source = ptr::null_mut();
    let mut source_pid = 0;
    let acquired =
        unsafe { super::GetSessionUserTokenWin(&mut raw_source, session, 0, &mut source_pid) };
    let source = OwnedHandle(HANDLE(raw_source.cast()));
    if acquired == 0 || source.0.is_invalid() {
        return Err(failure(
            "Unable to obtain current-session SYSTEM helper token",
        ));
    }
    // Existing bridge has an ordinary-user fallback. Never accept it as SYSTEM.
    require_system_session(source.0, session)?;
    let mut raw_primary = HANDLE::default();
    unsafe {
        DuplicateTokenEx(
            source.0,
            TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY,
            None,
            SecurityImpersonation,
            TokenPrimary,
            &mut raw_primary,
        )
    }
    .map_err(os_error)?;
    let primary = OwnedHandle(raw_primary);
    let mut desktop: Vec<u16> = r"winsta0\default".encode_utf16().chain(Some(0)).collect();
    let startup = STARTUPINFOW {
        lpDesktop: PWSTR(desktop.as_mut_ptr()),
        cb: size_of::<STARTUPINFOW>() as u32,
        ..unsafe { zeroed() }
    };
    let mut info = PROCESS_INFORMATION::default();
    unsafe {
        CreateProcessWithTokenW(
            primary.0,
            LOGON_WITH_PROFILE,
            PCWSTR(application.as_ptr()),
            Some(PWSTR(command.as_mut_ptr())),
            CREATE_SUSPENDED,
            None,
            PCWSTR::null(),
            &startup,
            &mut info,
        )
    }
    .map_err(os_error)?;
    let mut child = Child {
        process: OwnedHandle(info.hProcess),
        thread: OwnedHandle(info.hThread),
        started: false,
    };
    if child.process.0.is_invalid() || child.thread.0.is_invalid() {
        return Err(failure("Windows did not return valid helper handles"));
    }
    let mut raw_child_token = HANDLE::default();
    unsafe { OpenProcessToken(child.process.0, TOKEN_QUERY, &mut raw_child_token) }
        .map_err(os_error)?;
    let child_token = OwnedHandle(raw_child_token);
    require_system_session(child_token.0, session)?;
    impersonate.restore()?;
    debug.restore()?;
    match unsafe { ResumeThread(child.thread.0) } {
        1 => {}
        u32::MAX => return Err(io::Error::last_os_error()),
        _ => {
            return Err(failure(
                "Portable helper suspension state changed unexpectedly",
            ))
        }
    }
    child.started = true;
    // IPC ping/pong remains the existing authoritative helper-readiness check.
    Ok(())
}
