// SPDX-License-Identifier: AGPL-3.0-only
// FilDesk implementation from the documented Windows IP Helper API contract.
// No code from the grantless default_net Git dependency is included.

const ROUTE_ADDRESS: [u8; 4] = [8, 8, 8, 8];

fn format_mac(bytes: &[u8], reported_length: usize) -> Option<String> {
    if reported_length != 6 || bytes.len() < 6 {
        return None;
    }
    Some(
        bytes[..6]
            .iter()
            .map(|byte| format!("{byte:02X}"))
            .collect::<Vec<_>>()
            .join(":"),
    )
}

#[cfg(windows)]
pub(super) fn get_mac() -> std::io::Result<String> {
    use std::{
        io,
        mem::{size_of, MaybeUninit},
        ptr,
    };
    use winapi::{
        shared::{
            winerror::{ERROR_BUFFER_OVERFLOW, NO_ERROR},
            ws2def::AF_UNSPEC,
        },
        um::{
            iphlpapi::{GetAdaptersAddresses, GetBestInterface},
            iptypes::IP_ADAPTER_ADDRESSES_LH,
        },
    };

    let mut selected = 0u32;
    // A routing-table query, not a network probe or ARP request.
    let status = unsafe { GetBestInterface(u32::from_ne_bytes(ROUTE_ADDRESS), &mut selected) };
    if status != NO_ERROR {
        return Err(io::Error::from_raw_os_error(status as i32));
    }
    let mut required = 0u32;
    let status = unsafe {
        GetAdaptersAddresses(
            AF_UNSPEC as u32,
            0,
            ptr::null_mut(),
            ptr::null_mut(),
            &mut required,
        )
    };
    if status != ERROR_BUFFER_OVERFLOW {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "Adapter size query failed",
        ));
    }
    for _ in 0..3 {
        if required == 0 || required > 1024 * 1024 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "Adapter buffer size is invalid",
            ));
        }
        let unit = size_of::<IP_ADAPTER_ADDRESSES_LH>();
        let count = (required as usize).div_ceil(unit);
        let mut buffer: Vec<MaybeUninit<IP_ADAPTER_ADDRESSES_LH>> = Vec::with_capacity(count);
        buffer.resize_with(count, MaybeUninit::zeroed);
        let mut available = (count * unit) as u32;
        let start = buffer.as_mut_ptr() as *mut IP_ADAPTER_ADDRESSES_LH;
        let status = unsafe {
            GetAdaptersAddresses(AF_UNSPEC as u32, 0, ptr::null_mut(), start, &mut available)
        };
        if status == ERROR_BUFFER_OVERFLOW {
            required = available;
            continue;
        }
        if status != NO_ERROR {
            return Err(io::Error::from_raw_os_error(status as i32));
        }
        // Buffer bytes were zero-initialized before the IP Helper call.
        return unsafe { mac_from_adapters(start, count * unit, selected) };
    }
    Err(io::Error::new(
        io::ErrorKind::Interrupted,
        "Adapter list changed repeatedly",
    ))
}

#[cfg(windows)]
unsafe fn mac_from_adapters(
    start: *mut winapi::um::iptypes::IP_ADAPTER_ADDRESSES_LH,
    bytes: usize,
    selected: u32,
) -> std::io::Result<String> {
    use std::{io, mem::size_of, ptr};
    use winapi::um::iptypes::IP_ADAPTER_ADDRESSES_LH;
    let base = start as usize;
    let unit = size_of::<IP_ADAPTER_ADDRESSES_LH>();
    let mut node = start;
    for _ in 0..1024 {
        if node.is_null() {
            break;
        }
        let offset = (node as usize)
            .checked_sub(base)
            .filter(|offset| offset.checked_add(unit).is_some_and(|end| end <= bytes))
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "Adapter pointer is outside its buffer",
                )
            })?;
        // Copy rather than borrow: Windows may return differently aligned list nodes.
        let adapter =
            unsafe { ptr::read_unaligned((base + offset) as *const IP_ADAPTER_ADDRESSES_LH) };
        if unsafe { adapter.u.s().IfIndex } == selected {
            return format_mac(
                &adapter.PhysicalAddress,
                adapter.PhysicalAddressLength as usize,
            )
            .ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    "Adapter has no six-byte MAC address",
                )
            });
        }
        node = adapter.Next;
    }
    Err(io::Error::new(
        io::ErrorKind::NotFound,
        "Selected adapter not found",
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_route_and_fingerprint_bytes_preserve_73_contract() {
        assert_eq!(ROUTE_ADDRESS, [8, 8, 8, 8]);
        assert_eq!(
            format_mac(&[2, 0xab, 0xcd, 0xef, 0x90, 1, 0, 0], 6).as_deref(),
            Some("02:AB:CD:EF:90:01")
        );
    }

    #[test]
    fn non_six_byte_or_truncated_address_preserves_fallback_signal() {
        assert!(format_mac(&[0; 8], 0).is_none());
        assert!(format_mac(&[0; 8], 8).is_none());
        assert!(format_mac(&[0; 5], 6).is_none());
    }

    #[cfg(windows)]
    #[test]
    fn routing_index_selects_correct_adapter_and_rejects_missing_mac() {
        use std::mem::{size_of_val, zeroed};
        use winapi::um::iptypes::IP_ADAPTER_ADDRESSES_LH;
        let mut nodes: [IP_ADAPTER_ADDRESSES_LH; 2] = unsafe { zeroed() };
        unsafe {
            nodes[0].u.s_mut().IfIndex = 2;
            nodes[1].u.s_mut().IfIndex = 7;
        }
        nodes[0].Next = &mut nodes[1];
        nodes[0].PhysicalAddress = [1; 8];
        nodes[0].PhysicalAddressLength = 6;
        nodes[1].PhysicalAddress = [2, 0xab, 0xcd, 0xef, 0x90, 1, 0, 0];
        nodes[1].PhysicalAddressLength = 6;
        let bytes = size_of_val(&nodes);
        assert_eq!(
            unsafe { mac_from_adapters(nodes.as_mut_ptr(), bytes, 7) }.unwrap(),
            "02:AB:CD:EF:90:01"
        );
        assert!(unsafe { mac_from_adapters(nodes.as_mut_ptr(), bytes, 8) }.is_err());
        nodes[1].PhysicalAddressLength = 0;
        // Existing fingerprint caller maps this failure to its MAC fallback.
        assert_eq!(
            unsafe { mac_from_adapters(nodes.as_mut_ptr(), bytes, 7) }.unwrap_or_default(),
            ""
        );
    }

    #[cfg(windows)]
    #[test]
    fn malformed_adapter_pointer_does_not_escape_owned_buffer() {
        use std::mem::{size_of_val, zeroed};
        use winapi::um::iptypes::IP_ADAPTER_ADDRESSES_LH;
        let mut node: IP_ADAPTER_ADDRESSES_LH = unsafe { zeroed() };
        let mut foreign: IP_ADAPTER_ADDRESSES_LH = unsafe { zeroed() };
        node.Next = &mut foreign;
        assert_eq!(
            unsafe { mac_from_adapters(&mut node, size_of_val(&node), 99) }
                .unwrap_err()
                .kind(),
            std::io::ErrorKind::InvalidData
        );
    }
}
