#![cfg(not(windows))]
//! Linux-only algorithm benchmark. Never launches a payload or claims Windows timing.
#[path = "../src/bin_reader.rs"]
#[allow(dead_code)]
mod bin_reader;
#[path = "../src/fil_secure.rs"]
#[allow(dead_code)]
mod fil_secure;
use std::{io::Read, time::Instant};

fn alternate_decode(file: &bin_reader::BinaryData, size: u64, expected: &str, buffer: usize, reserve: bool) -> Vec<u8> {
    let mut bytes = Vec::new();
    if reserve { bytes.try_reserve_exact(size as usize).unwrap(); }
    brotli::Decompressor::new(file.raw, buffer).take(size + 1).read_to_end(&mut bytes).unwrap();
    assert_eq!(bytes.len() as u64, size);
    assert_eq!(fil_secure::hash(&bytes), expected);
    bytes
}

#[test]
#[ignore = "requires explicitly supplied accepted public artifact and trusted index; Linux only"]
fn benchmark_actual_payload_decode() {
    let index = std::fs::read_to_string(std::env::var("FIL_STARTUP_BENCH_INDEX").unwrap()).unwrap();
    let blob: &'static [u8] = Box::leak(std::fs::read(std::env::var("FIL_STARTUP_BENCH_EXE").unwrap()).unwrap().into_boxed_slice());
    let records: Vec<_> = index.lines().map(|line| {
        let p: Vec<_> = line.split('\t').collect();
        assert_eq!(p.len(), 5);
        let at: usize = p[1].parse().unwrap(); let len: usize = p[2].parse().unwrap();
        let file = bin_reader::BinaryData { path: p[0].into(), raw: &blob[at..at + len], md5_code: b"" };
        (file, p[3].parse::<u64>().unwrap(), p[4].to_owned())
    }).collect();
    assert_eq!(records.len(), 97);
    for iteration in 0..3 {
        // Alternate the order so one variant does not always get the first cache state.
        let order = if iteration % 2 == 0 { [0, 1, 2, 3] } else { [3, 2, 1, 0] };
        for variant in order {
            let start = Instant::now(); let mut expanded = 0;
            for (file, size, digest) in &records {
                let bytes = match variant {
                    0 => fil_secure::decode(file, *size, digest).unwrap(),
                    1 => alternate_decode(file, *size, digest, 4096, true),
                    2 => alternate_decode(file, *size, digest, 65536, true),
                    _ => alternate_decode(file, *size, digest, 65536, false),
                };
                expanded += bytes.len(); std::hint::black_box(bytes);
            }
            println!("STARTUP_BENCH variant={variant} iteration={iteration} files={} bytes={expanded} decode_us={}", records.len(), start.elapsed().as_micros());
        }
    }
}

#[test]
#[ignore="requires accepted public artifact/index and exclusive owned benchmark directory; Linux only"]
fn benchmark_actual_payload_readback() {
    let index=std::fs::read_to_string(std::env::var("FIL_STARTUP_BENCH_INDEX").unwrap()).unwrap();
    let blob=std::fs::read(std::env::var("FIL_STARTUP_BENCH_EXE").unwrap()).unwrap();
    let root=std::path::PathBuf::from(std::env::var("FIL_STARTUP_READBACK_DIR").unwrap());
    std::fs::create_dir(&root).unwrap();
    let mut files=Vec::new();
    for (i,line) in index.lines().enumerate() {
        let row:Vec<_>=line.split('\t').collect();
        let offset:usize=row[1].parse().unwrap();let length:usize=row[2].parse().unwrap();let size:u64=row[3].parse().unwrap();
        let raw=Box::leak(blob[offset..offset+length].to_vec().into_boxed_slice());
        let file=bin_reader::BinaryData{path:row[0].into(),raw,md5_code:b""};
        let bytes=fil_secure::decode(&file,size,row[4]).unwrap();
        let path=root.join(format!("payload-{i}"));
        let mut output=std::fs::OpenOptions::new().create_new(true).write(true).open(&path).unwrap();
        std::io::Write::write_all(&mut output,&bytes).unwrap();output.sync_all().unwrap();
        files.push((path,bytes));
    }
    assert_eq!(files.len(),97);
    for iteration in 0..5 {
        let order=if iteration%2==0 {[0,1]}else{[1,0]};
        for variant in order {
            let start=Instant::now();let mut total=0;
            for (path,expected) in &files {
                let mut file=std::fs::File::open(path).unwrap();
                if variant==0 {let mut stored=Vec::new();(&mut file).take(expected.len() as u64+1).read_to_end(&mut stored).unwrap();assert_eq!(&stored,expected);std::hint::black_box(stored);}
                else {fil_secure::verify_readback(&mut file,expected).unwrap();}
                total+=expected.len();
            }
            println!("STARTUP_READBACK variant={variant} iteration={iteration} files={} bytes={total} readback_us={}",files.len(),start.elapsed().as_micros());
        }
    }
    for (path,_) in files {std::fs::remove_file(path).unwrap();}std::fs::remove_dir(root).unwrap();
}
