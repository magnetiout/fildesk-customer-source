//! Static integration contracts over the actual authorization hooks. These are
//! not socket/GUI/Windows tests; native runtime acceptance remains separate.
#[path = "../src/fil_support_consent.rs"]
mod consent;

const CONNECTION: &str = include_str!("../src/server/connection.rs");
const CORE: &str = include_str!("../src/core_main.rs");
const WINDOWS: &str = include_str!("../src/platform/windows.rs");
fn section<'a>(source: &'a str, start: &str, end: &str) -> &'a str {
    let tail = &source[source.find(start).expect("actual hook exists")..];
    &tail[..tail.find(end).expect("actual hook end exists")]
}
#[test]
fn final_authorization_and_cm_click_cannot_bypass_customer_prerequisites() {
    let completion = section(
        CONNECTION,
        "async fn send_logon_response_and_keep_alive",
        "password::update_temporary_password()",
    );
    assert!(
        completion
            .find("fil_customer_consent.may_authorize()")
            .unwrap()
            < completion.find("self.authorized = true").unwrap()
    );
    assert_eq!(CONNECTION.matches("self.authorized = true").count(), 1);
    let ipc = section(CONNECTION, "ipc::Data::Authorize =>", "ipc::Data::Close =>");
    assert!(
        ipc.find("fil_customer_consent.approve_locally()").unwrap()
            < ipc.find("send_logon_response_and_keep_alive()").unwrap()
    );
    assert!(ipc.contains("if !crate::fil_remote::requires_customer_consent()"));
    assert!(ipc.contains("conn.require_2fa.take()"));
    assert!(ipc.contains("password::approve_mode() == ApproveMode::Password"));
    assert!(ipc.contains("conn.on_close(\"password-only approval policy\""));
    assert!(completion.contains("fil_customer_consent.has_verified_credential()"));
    assert!(completion.contains("may_reuse_2fa && self.is_recent_session(true)"));
}
#[test]
fn positive_credential_branches_and_retry_switch_boundaries_are_wired() {
    let recent = section(
        CONNECTION,
        "} else if self.is_recent_session(false)",
        "} else if lr.password.is_empty()",
    );
    assert!(recent.contains("fil_customer_consent.credential_verified()"));
    let check = section(
        CONNECTION,
        "if !self.validate_password(allow_logon_screen_password)",
        "Some(message::Union::Auth2fa(tfa))",
    );
    assert!(
        check.find("} else {").unwrap()
            < check
                .find("fil_customer_consent.credential_verified()")
                .unwrap()
    );
    assert_eq!(
        CONNECTION
            .matches("fil_customer_consent.credential_verified()")
            .count(),
        2
    );
    let login = section(
        CONNECTION,
        "if let Some(message::Union::LoginRequest(lr)) = msg.union",
        "self.awaiting_2fa = false",
    );
    assert!(login.contains("fil_customer_consent.reset()"));
    let switch = section(
        CONNECTION,
        "Some(message::Union::SwitchSidesResponse(_s))",
        "if let Some(lr)",
    );
    assert!(switch.contains("requires_customer_consent()"));
    assert!(switch.contains("return false"));
}
#[test]
fn portable_install_guards_precede_platform_side_effects() {
    let cli = section(
        CORE,
        "crate::load_custom_client();",
        "let mut args = Vec::new()",
    );
    assert!(
        cli.find("customer_disallowed_command").unwrap()
            < cli.find("windows::bootstrap()").unwrap()
    );
    let install = section(WINDOWS, "pub fn install_me(", "let uninstall_str");
    assert!(
        install.find("requires_customer_consent()").unwrap()
            < install.find("get_install_info()").unwrap()
    );
    let service = section(WINDOWS, "pub fn install_service()", "let (_, path");
    assert!(
        service.find("requires_customer_consent()").unwrap()
            < service.find("InstallingService::new()").unwrap()
    );
}

#[test]
fn service_binary_and_autostart_cleanup_cannot_mutate_customer_installation() {
    let service = section(WINDOWS, "pub fn start_os_service()", "const SERVICE_TYPE");
    assert!(
        service.find("requires_customer_consent()").unwrap()
            < service.find("service_dispatcher::start").unwrap()
    );
    assert_eq!(
        CORE.matches("if !crate::fil_remote::requires_customer_consent() {\n")
            .count(),
        2
    );
    assert_eq!(CORE.matches("check_autostart_config()").count(), 2);
    let stop = section(
        WINDOWS,
        "pub fn uninstall_service(",
        "fn get_install_service_commands",
    );
    assert!(
        stop.find("requires_customer_consent()").unwrap()
            < stop.find("Config::set_option").unwrap()
    );
}
