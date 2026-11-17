//! Source wiring regression, not an IPC socket or Windows acceptance test.
const CM: &str = include_str!("../src/ui_cm_interface.rs");
const CONNECTION: &str = include_str!("../src/server/connection.rs");
const MODEL: &str = include_str!("../flutter/lib/models/server_model.dart");

#[test]
fn customer_click_requests_authorization_and_native_success_confirms_it() {
    let request = CM.split("pub fn authorize(id: i32)").nth(1).unwrap()
        .split("pub fn close(").next().unwrap();
    assert!(request.contains("if !crate::fil_remote::requires_customer_consent()"));
    assert!(request.contains("client.tx.send(Data::Authorize)"));
    let success = CONNECTION.split("self.authorized = true;").nth(1).unwrap()
        .split("password::update_temporary_password()").next().unwrap();
    assert!(success.contains("self.try_start_cm(self.lr.my_id.clone(), self.lr.my_name.clone(), true)"));
    let ui = MODEL.split("void sendLoginResponse(Client client, bool res)").nth(1).unwrap()
        .split("void onClientRemove").next().unwrap();
    assert!(ui.contains("if (!isDesktop || !bind.isIncomingOnly())"));
    // Existing authenticated Login IPC is consumed on each task-run iteration.
    assert!(CM.contains("Data::Login{id, is_file_transfer"));
    assert!(MODEL.contains("if (client.authorized)"));
}
