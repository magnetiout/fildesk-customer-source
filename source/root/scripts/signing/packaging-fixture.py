"""Generate test-only payload and prove byte-preserving compression of signed input."""
import importlib.util, pathlib
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('packer',root/'client/libs/portable/generate.py')
packer=importlib.util.module_from_spec(spec);spec.loader.exec_module(packer)
table=packer.generate_md5_table(str(root/'build/portable-fixture'),1)
packer.write_package_metadata(table,str(root/'client/libs/portable'),'./FilDesk.exe')
packer.write_app_metadata(str(root/'client/libs/portable'))
content=packer.brotli.decompress(next(iter(table.values()))[0])
(root/'build/portable-restored.exe').write_bytes(content)
