// SPDX-License-Identifier: AGPL-3.0-only
// Native OS contracts, independently implemented for FilDesk. Preserve the
// fingerprint input and leave final fallback/padding in the existing caller.
use std::io;

#[cfg(any(windows, test))]
#[path = "fingerprint_windows_mac.rs"]
mod windows_mac;

#[cfg(any(target_os = "linux", target_os = "macos", test))]
fn valid_mac(bytes: &[u8]) -> bool {
    bytes.len() == 17
        && bytes.iter().enumerate().all(|(index, byte)| {
            if index % 3 == 2 {
                *byte == b':'
            } else {
                byte.is_ascii_hexdigit()
            }
        })
}

#[cfg(any(target_os = "linux", test))]
fn linux_default_interface(routes: &str) -> Option<&str> {
    routes.lines().skip(1).find_map(|line| {
        let mut fields = line.split_whitespace();
        let interface = fields.next()?;
        (fields.next()? == "00000000"
            && !interface.contains('/')
            && interface != "."
            && interface != "..")
            .then_some(interface)
    })
}

#[cfg(any(target_os = "macos", test))]
fn macos_default_interface(route: &str) -> Option<&str> {
    route.lines().find_map(|line| {
        let (key, value) = line.split_once(':')?;
        (key.trim() == "interface")
            .then(|| value.split_whitespace().next())
            .flatten()
    })
}

#[cfg(any(target_os = "macos", test))]
fn macos_mac(output: &str) -> Option<String> {
    output
        .as_bytes()
        .windows(17)
        .find(|bytes| valid_mac(bytes))
        .and_then(|bytes| std::str::from_utf8(bytes).ok())
        .map(str::to_owned)
}

pub(super) fn get_mac() -> io::Result<String> {
    #[cfg(windows)]
    {
        windows_mac::get_mac()
    }
    #[cfg(target_os = "linux")]
    {
        let routes = std::fs::read_to_string("/proc/net/route")?;
        let interface = linux_default_interface(&routes).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "Default network interface is unavailable",
            )
        })?;
        let address = std::fs::read_to_string(
            std::path::Path::new("/sys/class/net")
                .join(interface)
                .join("address"),
        )?;
        let address = address.trim();
        if valid_mac(address.as_bytes()) {
            Ok(address.to_owned())
        } else {
            Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "Default adapter MAC is invalid",
            ))
        }
    }
    #[cfg(target_os = "macos")]
    {
        let route = std::process::Command::new("route")
            .args(["-n", "get", "default"])
            .output()?;
        let route = String::from_utf8(route.stdout).map_err(|_| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "Default route output is invalid",
            )
        })?;
        let interface = macos_default_interface(&route).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "Default network interface is unavailable",
            )
        })?;
        let address = std::process::Command::new("networksetup")
            .args(["-getmacaddress", interface])
            .output()?;
        let address = String::from_utf8(address.stdout)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "MAC output is invalid"))?;
        macos_mac(&address).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "Default adapter MAC is unavailable",
            )
        })
    }
    #[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
    {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "No native MAC provider for this platform",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linux_uses_first_default_route_and_keeps_mac_case() {
        let routes =
            "Iface Destination Gateway\neth0 01020304 0\nwlan0 00000000 1\neth0 00000000 2\n";
        assert_eq!(linux_default_interface(routes), Some("wlan0"));
        assert!(valid_mac("aB:cd:01:23:45:EF".as_bytes()));
        assert_eq!("aB:cd:01:23:45:EF\n".trim(), "aB:cd:01:23:45:EF");
    }

    #[test]
    fn macos_route_and_first_six_byte_mac_preserve_spelling() {
        assert_eq!(
            macos_default_interface("route to: default\n interface: en7\n flags: UP\n"),
            Some("en7")
        );
        assert_eq!(
            macos_mac("Ethernet Address: aB:cd:01:23:45:EF (Device: en7)"),
            Some("aB:cd:01:23:45:EF".into())
        );
    }

    #[test]
    fn missing_or_invalid_data_returns_fallback_signal() {
        assert!(linux_default_interface("Iface Destination\neth0 01020304\n").is_none());
        assert!(linux_default_interface("Iface Destination\n../bad 00000000\n").is_none());
        assert!(macos_default_interface("route to: default\n").is_none());
        assert!(macos_mac("Ethernet Address: unavailable").is_none());
        assert!(!valid_mac(b"00:11:22:33:44"));
    }
}
