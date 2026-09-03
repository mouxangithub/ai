"""Unit tests for bundle manifest, packer, loader, and store."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai.acp.protocol import AcpPackage, AcpPackageMetadata
from ai.bundle.loader import BundleInstallError, BundleLoader
from ai.bundle.manifest import BundleManifest, BundlePackageRef
from ai.bundle.packer import BundlePacker
from ai.bundle.store import BundleStore


class TestBundleManifest(unittest.TestCase):
  def test_round_trip(self) -> None:
    manifest = BundleManifest(
      id="bundle-1",
      name="Bundle One",
      version="1.0.0",
      description="A bundle",
      author="tester",
      created_at="2026-09-02T00:00:00Z",
      packages=[BundlePackageRef(id="pkg.a", version="0.1.0", path="packages/pkg.a")],
      files=["readme.md"],
      extra={"note": "x"},
    )
    data = manifest.to_dict()
    restored = BundleManifest.from_dict(data)
    self.assertEqual(restored, manifest)


class TestBundlePacker(unittest.TestCase):
  def test_pack_directory(self) -> None:
    with TemporaryDirectory() as tmp:
      source = Path(tmp) / "src"
      source.mkdir()
      (source / "hello.txt").write_text("hello", encoding="utf-8")
      out = Path(tmp) / "bundle.zip"
      packer = BundlePacker()
      manifest = packer.pack(source, out)
      self.assertEqual(manifest.files, ["hello.txt"])
      self.assertTrue(out.is_file())

      import zipfile
      with zipfile.ZipFile(out, "r") as archive:
        names = set(archive.namelist())
      self.assertIn("hello.txt", names)
      self.assertIn("bundle.json", names)


class TestBundleLoader(unittest.TestCase):
  def test_load_and_install(self) -> None:
    with TemporaryDirectory() as tmp:
      source = Path(tmp) / "src"
      source.mkdir()
      (source / "data.txt").write_text("data", encoding="utf-8")
      out = Path(tmp) / "bundle.zip"
      packer = BundlePacker()
      packer.pack(source, out)

      loader = BundleLoader()
      manifest, extract_dir = loader.load(out)
      self.assertEqual(manifest.files, ["data.txt"])
      self.assertTrue((extract_dir / "data.txt").is_file())

      install_dir = Path(tmp) / "installed"
      installed = loader.install(out, install_dir)
      self.assertEqual(installed.id, manifest.id)
      self.assertTrue((install_dir / "data.txt").is_file())

  def test_load_missing(self) -> None:
    with TemporaryDirectory() as tmp:
      loader = BundleLoader()
      with self.assertRaises(BundleInstallError):
        loader.load(Path(tmp) / "nope.zip")

  def test_install_acp_packages(self) -> None:
    with TemporaryDirectory() as tmp:
      source = Path(tmp) / "src"
      pkg_dir = source / "packages" / "pkg.a"
      pkg_dir.mkdir(parents=True)
      package = AcpPackage(
        metadata=AcpPackageMetadata(id="pkg.a", name="Pkg A", version="0.1.0"),
      )
      (pkg_dir / "acp.json").write_text(json.dumps(package.to_dict()), encoding="utf-8")

      manifest = BundleManifest(
        id="with-acp",
        name="With ACP",
        version="1.0.0",
        packages=[BundlePackageRef(id="pkg.a", version="0.1.0", path="packages/pkg.a")],
      )
      out = Path(tmp) / "bundle.zip"
      BundlePacker().pack(source, out, manifest=manifest)

      install_dir = Path(tmp) / "installed"
      packages = BundleLoader().install_acp_packages(out, install_dir)
      self.assertEqual(len(packages), 1)
      self.assertEqual(packages[0].id, "pkg.a")


class TestBundleStore(unittest.TestCase):
  def test_save_list_get_remove(self) -> None:
    with TemporaryDirectory() as tmp:
      store = BundleStore(store_dir=tmp)
      source = Path(tmp) / "src"
      source.mkdir()
      (source / "note.txt").write_text("note", encoding="utf-8")

      manifest = BundleManifest(id="stored", name="Stored", version="1.0.0")
      path = store.save_bundle(source, manifest=manifest)
      self.assertTrue(path.is_file())

      manifests = store.list_bundles()
      self.assertEqual(len(manifests), 1)
      self.assertEqual(manifests[0].id, "stored")

      got = store.get_bundle("stored")
      self.assertIsNotNone(got)
      self.assertEqual(got.id if got else None, "stored")

      self.assertTrue(store.remove_bundle("stored"))
      self.assertEqual(store.list_bundles(), [])


if __name__ == "__main__":
  unittest.main()
