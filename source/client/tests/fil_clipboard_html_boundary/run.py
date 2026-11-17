#!/usr/bin/env python3
"""Test pinned clipboard-win's actual HTML parser using synthetic OS buffers only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--client', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
client = a.client.resolve(strict=True)
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
lock = (client / 'Cargo.lock').read_text(encoding='utf-8')
locked = ('name = "clipboard-win"\nversion = "5.4.2"\n'
          'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
          'checksum = "39ed3668f121a65e4ce95efeba22ad1f8ad6c6628397a5dd773118514a5e1804"')
if locked not in lock:
    raise SystemExit('Reviewed clipboard-win 5.4.2 lock entry differs')
home = Path(os.environ.get('CARGO_HOME', str(Path.home() / '.cargo')))
files = list((home / 'registry/src').glob('*/clipboard-win-5.4.2/src/raw.rs'))
expected = '4e212e7778b66c9ab9c61b2a6acf0e776a20064d458c398fc492945c5459a5c9'
files = [f for f in files if hashlib.sha256(f.read_bytes()).hexdigest() == expected]
if not files:
    raise SystemExit('Verified dependency source missing: run cargo fetch --locked first')
raw = files[0].read_text(encoding='utf-8')
start = raw.index('pub fn get_html(')
end = raw.index('\n}\n', start) + 3
function = raw[start:end]
preamble = '''extern crate alloc;
use core::{hint, ptr, slice, str};
use std::cell::RefCell;
type SysResult<T> = Result<T, u32>;
fn invalid_data() -> u32 { 13 }
mod html {
    pub const SEP: char = ':';
    pub const START_FRAGMENT: &str = "StartFragment";
    pub const END_FRAGMENT: &str = "EndFragment";
}
thread_local! { static BUFFER: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) }; }
struct RawMem(ptr::NonNull<u8>);
impl RawMem {
    fn from_borrowed(p: ptr::NonNull<u8>) -> Self { Self(p) }
    fn get(&self) -> *mut u8 { self.0.as_ptr() }
    fn lock(&self) -> SysResult<(ptr::NonNull<u8>, ())> { Ok((self.0, ())) }
}
fn get_clipboard_data(_: u32) -> SysResult<ptr::NonNull<u8>> {
    BUFFER.with(|b| ptr::NonNull::new(b.borrow_mut().as_mut_ptr()).ok_or(13))
}
#[allow(non_snake_case)]
fn GlobalSize(_: *mut u8) -> usize { BUFFER.with(|b| b.borrow().len()) }
'''
tests = r'''
#[cfg(test)] mod tests {
    use super::*;
    fn run(start: usize, end: usize, out: &mut Vec<u8>) -> SysResult<usize> {
        let header = format!("StartFragment:{start:010}\r\nEndFragment:{end:010}\r\n");
        let mut data = header.into_bytes();
        data.extend_from_slice("<b>hello</b>".as_bytes());
        BUFFER.with(|b| *b.borrow_mut() = data);
        get_html(1, out)
    }
    #[test] fn valid_fragment_appends_without_overwriting_prefix() {
        let header_len = "StartFragment:0000000000\r\nEndFragment:0000000000\r\n".len();
        let mut out = b"prefix:".to_vec();
        assert_eq!(run(header_len, header_len + 12, &mut out), Ok(12));
        assert_eq!(out, b"prefix:<b>hello</b>");
    }
    #[test] fn out_of_bounds_fragment_is_rejected_without_exposing_memory() {
        let mut out = b"prefix".to_vec();
        assert_eq!(run(1_000_000_000, 1_000_000_016, &mut out), Err(13));
        assert_eq!(out, b"prefix");
    }
    #[test] fn reversed_fragment_is_rejected_without_modifying_output() {
        let mut out = b"prefix".to_vec();
        assert_eq!(run(60, 50, &mut out), Err(13));
        assert_eq!(out, b"prefix");
    }
}
'''
fixture = out / 'fixture'
fixture.mkdir()
(fixture / 'src').mkdir()
(fixture / 'src/lib.rs').write_text(preamble + function + tests, encoding='utf-8')
(fixture / 'Cargo.toml').write_text('[package]\nname = "fil-clipboard-html-boundary"\nversion = "0.1.0"\nedition = "2021"\n\n[workspace]\n', encoding='utf-8')
(fixture / 'Cargo.lock').write_text('version = 3\n\n[[package]]\nname = "fil-clipboard-html-boundary"\nversion = "0.1.0"\n', encoding='utf-8')
command = ['cargo', 'test', '--locked', '--offline', '--manifest-path', str(fixture / 'Cargo.toml'), '--', '--test-threads=1']
with (out / 'tests.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, cwd=client, stdout=log, stderr=subprocess.STDOUT)
text = (out / 'tests.log').read_text(encoding='utf-8')
ok = result.returncode == 0 and 'test result: ok. 3 passed; 0 failed;' in text
report = {'status': 'PASS' if ok else 'FAIL', 'tests': 3 if ok else None,
          'command': command, 'exitCode': result.returncode,
          'dependency': 'clipboard-win 5.4.2', 'sourceFileSHA256': expected,
          'testedFunctionSHA256': hashlib.sha256(function.encode()).hexdigest(),
          'coverage': 'Exact pinned get_html function with synthetic OS byte-buffer boundary; valid append, malformed offsets, reversed offsets',
          'notVerified': ['Actual Windows clipboard API integration', 'Physical remote clipboard transfer'],
          'systemClipboardReadOrWritten': False, 'platform': sys.platform}
(out / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
sys.exit(0 if ok else result.returncode or 1)
