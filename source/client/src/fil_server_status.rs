//! Read-only NAT-service availability, deliberately NOT server identity/session authentication.
//! Wire contract: common rendezvous.proto TestNatRequest(20) / TestNatResponse(21),
//! framed by BytesCodec. No peer registration, credentials, or configuration writes.
use std::{
    io::{self, Read, Write},
    net::{SocketAddr, TcpStream},
    sync::{Arc, Mutex, OnceLock},
    time::{Duration, Instant},
};

const LEASE: Duration = Duration::from_secs(12);
const PROBE_LIMIT: Duration = Duration::from_secs(3);
const FRESH: Duration = Duration::from_secs(15);
const MAX_FRAME: usize = 4096;

#[derive(Clone, Debug)]
pub struct Snapshot {
    pub state: &'static str,
    pub reason: &'static str,
    pub available: bool,
    pub checked_ago_ms: Option<u64>,
    pub retry_after_ms: u64,
}
impl Snapshot {
    fn pending(state: &'static str, reason: &'static str) -> Self {
        Self {
            state,
            reason,
            available: false,
            checked_ago_ms: None,
            retry_after_ms: 0,
        }
    }
}
struct Tracker {
    target: String,
    key_configuration: String,
    generation: u64,
    last_poll: Instant,
    next_probe: Instant,
    last_check: Option<Instant>,
    running: bool,
    failures: u32,
    value: Snapshot,
}
struct Monitor(Mutex<Tracker>);
static MONITOR: OnceLock<Arc<Monitor>> = OnceLock::new();

/// One worker shared by all status widgets. Polling renews a short UI-owned lease;
/// disposal stops polling and the worker closes its socket/exits on lease expiry.
/// Config changes invalidate prior results, including an in-flight response.
pub fn poll(id_server: &str, key_configuration: &str, key_configuration_valid: bool) -> Snapshot {
    let monitor = MONITOR
        .get_or_init(|| {
            Arc::new(Monitor(Mutex::new(Tracker {
                target: String::new(),
                key_configuration: String::new(),
                generation: 0,
                last_poll: Instant::now(),
                next_probe: Instant::now(),
                last_check: None,
                running: false,
                failures: 0,
                value: Snapshot::pending("connecting", "pending"),
            })))
        })
        .clone();
    let now = Instant::now();
    let Ok(mut t) = monitor.0.lock() else {
        return Snapshot::pending("disconnected", "monitor_unavailable");
    };
    // Only numeric addresses: never block the UI thread on DNS resolution.
    let target = nat_address(id_server);
    let effective = if key_configuration_valid {
        id_server
    } else {
        ""
    };
    if t.target != effective
        || t.key_configuration != key_configuration
        || now.duration_since(t.last_poll) > LEASE
    {
        t.target = effective.to_owned();
        t.key_configuration = key_configuration.to_owned();
        t.generation = t.generation.wrapping_add(1);
        t.last_check = None;
        t.next_probe = now;
        t.failures = 0;
        t.value = Snapshot::pending("connecting", "pending");
    }
    t.last_poll = now;
    if !key_configuration_valid {
        t.value = Snapshot::pending("identity_failed", "invalid_configuration_key");
    } else if target.is_err() {
        t.value = Snapshot::pending("identity_unavailable", "unsupported_server_address");
    } else {
        if t.last_check
            .map(|v| now.duration_since(v) > FRESH)
            .unwrap_or(false)
        {
            t.value = Snapshot::pending("reconnecting", "observation_expired");
        }
        if !t.running {
            t.running = true;
            let worker = monitor.clone();
            if std::thread::Builder::new()
                .name("fil-server-status".into())
                .spawn(move || run(worker))
                .is_err()
            {
                t.running = false;
                t.value = Snapshot::pending("disconnected", "worker_unavailable");
            }
        }
    }
    let mut value = t.value.clone();
    value.checked_ago_ms = t
        .last_check
        .map(|v| now.duration_since(v).as_millis() as u64);
    value.retry_after_ms = t.next_probe.saturating_duration_since(now).as_millis() as u64;
    value
}

fn nat_address(id_server: &str) -> Result<SocketAddr, &'static str> {
    let mut addr: SocketAddr = id_server
        .parse()
        .map_err(|_| "unsupported_server_address")?;
    if addr.port() <= 1 || addr.ip().is_unspecified() || addr.ip().is_multicast() {
        return Err("unsupported_server_address");
    }
    addr.set_port(addr.port() - 1);
    Ok(addr)
}
fn backoff(failures: u32) -> Duration {
    Duration::from_secs((1u64 << failures.min(5)).min(30))
}
fn current(m: &Monitor, generation: u64) -> bool {
    m.0.lock()
        .map(|t| t.generation == generation && t.last_poll.elapsed() < LEASE)
        .unwrap_or(false)
}
fn fresh_available(t: &Tracker, now: Instant) -> bool {
    t.value.available
        && t.last_check
            .map(|checked| now.duration_since(checked) <= FRESH)
            .unwrap_or(false)
}

fn run(m: Arc<Monitor>) {
    loop {
        let (generation, address, wait) = {
            let Ok(mut t) = m.0.lock() else {
                return;
            };
            if t.last_poll.elapsed() >= LEASE || t.target.is_empty() {
                t.running = false;
                return;
            }
            let Ok(address) = nat_address(&t.target) else {
                t.running = false;
                return;
            };
            let wait = t.next_probe.saturating_duration_since(Instant::now());
            // A background heartbeat is not a reconnect while the previous
            // unsigned availability sample is still fresh.
            if wait.is_zero() && !fresh_available(&t, Instant::now()) {
                t.value = Snapshot::pending(
                    if t.last_check.is_some() {
                        "reconnecting"
                    } else {
                        "connecting"
                    },
                    "pending",
                );
            }
            (t.generation, address, wait)
        };
        if !wait.is_zero() {
            std::thread::sleep(wait.min(Duration::from_millis(100)));
            continue;
        }
        let result = probe(address, || !current(&m, generation), PROBE_LIMIT);
        let Ok(mut t) = m.0.lock() else {
            return;
        };
        if t.generation != generation {
            continue;
        }
        if t.last_poll.elapsed() >= LEASE {
            t.running = false;
            return;
        }
        t.last_check = Some(Instant::now());
        match result {
            Ok(()) => {
                t.failures = 0;
                t.value = Snapshot {
                    state: "available_unverified",
                    reason: "unsigned_nat_response",
                    available: true,
                    checked_ago_ms: Some(0),
                    retry_after_ms: 0,
                };
                t.next_probe = Instant::now() + Duration::from_secs(10);
            }
            Err(reason) => {
                t.failures = t.failures.saturating_add(1);
                t.value = Snapshot::pending("disconnected", reason);
                t.next_probe = Instant::now() + backoff(t.failures);
            }
        }
    }
}

/// Bounded, unsigned protocol response. Success proves availability ONLY; the
/// configured Ed25519 key is intentionally neither sent nor treated as verified.
fn probe(
    address: SocketAddr,
    cancelled: impl Fn() -> bool,
    budget: Duration,
) -> Result<(), &'static str> {
    let deadline = Instant::now() + budget;
    if cancelled() {
        return Err("cancelled");
    }
    let mut stream = TcpStream::connect_timeout(&address, budget)
        .map_err(|_| "unreachable")?;
    stream
        .set_read_timeout(Some(Duration::from_millis(100)))
        .map_err(|_| "io_error")?;
    stream
        .set_write_timeout(Some(Duration::from_millis(100)))
        .map_err(|_| "io_error")?;
    // TestNatRequest empty message, union field 20; 3-byte payload frame.
    stream
        .write_all(&[12, 0xa2, 1, 0])
        .map_err(|_| "io_error")?;
    let mut read = |bytes: &mut [u8]| -> Result<(), &'static str> {
        let mut offset = 0;
        while offset < bytes.len() {
            if cancelled() {
                return Err("cancelled");
            }
            if Instant::now() >= deadline {
                return Err("timeout");
            }
            match stream.read(&mut bytes[offset..]) {
                Ok(0) => return Err("closed"),
                Ok(n) => offset += n,
                Err(e)
                    if matches!(
                        e.kind(),
                        io::ErrorKind::TimedOut
                            | io::ErrorKind::WouldBlock
                            | io::ErrorKind::Interrupted
                    ) => {}
                Err(_) => return Err("io_error"),
            }
        }
        Ok(())
    };
    let mut head = [0u8; 4];
    read(&mut head[..1])?;
    let width = ((head[0] & 3) + 1) as usize;
    read(&mut head[1..width])?;
    let length = (u32::from_le_bytes(head) >> 2) as usize;
    if length == 0 || length > MAX_FRAME {
        return Err("invalid_response");
    }
    let mut body = vec![0; length];
    read(&mut body)?;
    if valid_response(&body) {
        Ok(())
    } else {
        Err("invalid_response")
    }
}
fn varint(bytes: &[u8], cursor: &mut usize) -> Option<u64> {
    let mut result = 0u64;
    for i in 0..10 {
        let b = *bytes.get(*cursor)?;
        *cursor += 1;
        if i == 9 && b > 1 {
            return None;
        }
        result |= ((b & 127) as u64) << (7 * i);
        if b < 128 {
            return Some(result);
        }
    }
    None
}
fn valid_response(bytes: &[u8]) -> bool {
    let mut c = 0;
    // Exactly one TestNatResponse union; refuse other/ambiguous response kinds.
    if varint(bytes, &mut c) != Some((21 << 3) | 2) {
        return false;
    }
    let Some(len) = varint(bytes, &mut c).and_then(|v| usize::try_from(v).ok()) else {
        return false;
    };
    if len != bytes.len().saturating_sub(c) {
        return false;
    }
    let body = &bytes[c..];
    let mut c = 0;
    let mut port = None;
    let mut fields = 0;
    while c < body.len() {
        fields += 1;
        if fields > 64 {
            return false;
        }
        match varint(body, &mut c) {
            Some(8) if port.is_none() => {
                port = varint(body, &mut c);
            }
            // Optional ConfigUpdate is opaque and NEVER applied by this probe.
            Some(18) => {
                let Some(n) = varint(body, &mut c).and_then(|v| usize::try_from(v).ok()) else {
                    return false;
                };
                let Some(end) = c.checked_add(n).filter(|v| *v <= body.len()) else {
                    return false;
                };
                c = end;
            }
            _ => return false,
        }
    }
    matches!(port, Some(1..=65535))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    #[test]
    fn unsigned_response_is_only_availability_and_decoder_is_bounded() {
        assert!(valid_response(&[0xaa, 1, 3, 8, 0xa0, 1]));
        for bad in [
            &[][..],
            &[0xaa, 1, 2, 8, 0],
            &[0xaa, 1, 2, 8, 1, 0],
            &[0xa2, 1, 0],
            &[0xaa, 1, 4, 8, 1, 8, 2],
        ] {
            assert!(!valid_response(bad));
        }
        let mut c = 0;
        assert!(varint(&[255; 11], &mut c).is_none());
        assert_eq!(backoff(1), Duration::from_secs(2));
        assert_eq!(backoff(u32::MAX), Duration::from_secs(30));
        assert!(nat_address("wss://example.invalid").is_err());
        assert!(nat_address("127.0.0.1:1").is_err());
    }
    #[test]
    fn actual_loopback_protocol_response_timeout_and_cancellation() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let server = std::thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            let mut request = [0; 4];
            socket.read_exact(&mut request).unwrap();
            assert_eq!(request, [12, 0xa2, 1, 0]);
            socket.write_all(&[24, 0xaa, 1, 3, 8, 0xa0, 1]).unwrap();
        });
        assert_eq!(probe(address, || false, Duration::from_millis(500)), Ok(()));
        server.join().unwrap();
        assert_eq!(
            probe(address, || true, Duration::from_millis(200)),
            Err("cancelled")
        );
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let server = std::thread::spawn(move || {
            let (_socket, _) = listener.accept().unwrap();
            std::thread::sleep(Duration::from_millis(350));
        });
        let start = Instant::now();
        assert_eq!(
            probe(address, || false, Duration::from_millis(120)),
            Err("timeout")
        );
        assert!(start.elapsed() < Duration::from_millis(320));
        server.join().unwrap();
        assert_eq!(
            probe(address, || false, Duration::from_millis(100)),
            Err("unreachable")
        );
    }
    #[test]
    fn old_generation_and_abandoned_widget_cannot_keep_observation_live() {
        let now = Instant::now();
        let m = Monitor(Mutex::new(Tracker {
            target: "127.0.0.1:2".into(),
            key_configuration: String::new(),
            generation: 2,
            last_poll: now,
            next_probe: now,
            last_check: None,
            running: false,
            failures: 0,
            value: Snapshot::pending("connecting", "pending"),
        }));
        assert!(current(&m, 2));
        assert!(!current(&m, 1));
        {
            let mut t = m.0.lock().unwrap();
            t.value.available = true;
            t.last_check = Some(now);
            assert!(fresh_available(&t, now + Duration::from_secs(10)));
            assert!(!fresh_available(&t, now + FRESH + Duration::from_millis(1)));
        }
        m.0.lock().unwrap().last_poll = now - LEASE;
        assert!(!current(&m, 2));

        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let mut id_address = listener.local_addr().unwrap();
        id_address.set_port(id_address.port() + 1);
        let server = std::thread::spawn(move || {
            for _ in 0..2 {
                let (mut socket, _) = listener.accept().unwrap();
                let mut request = [0; 4];
                socket.read_exact(&mut request).unwrap();
                assert_eq!(request, [12, 0xa2, 1, 0]);
                socket.write_all(&[24, 0xaa, 1, 3, 8, 0xa0, 1]).unwrap();
            }
        });
        for key in [
            "7SzJDmRjxtGAqJip+9LGZsV4YIdLyZIm+uQbX+weJJQ=",
            "L1lzTqPtBsUnWZLz7D8p5h+iYf83hHc6irFmTiTljXE=",
        ] {
            let initial = poll(&id_address.to_string(), key, true);
            assert!(!initial.available); // Changed key invalidates the previous sample immediately.
            let start = Instant::now();
            loop {
                let sample = poll(&id_address.to_string(), key, true);
                if sample.available {
                    assert_eq!(sample.state, "available_unverified");
                    assert_eq!(sample.reason, "unsigned_nat_response");
                    break;
                }
                assert!(start.elapsed() < Duration::from_secs(2));
                std::thread::sleep(Duration::from_millis(10));
            }
        }
        assert_eq!(
            poll(&id_address.to_string(), "malformed", false).state,
            "identity_failed"
        );
        server.join().unwrap();
    }
}
