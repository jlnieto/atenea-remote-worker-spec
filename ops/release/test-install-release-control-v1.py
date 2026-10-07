#!/usr/bin/env python3
"""Installer contract tests. No root configuration, installation or restart."""
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("install-release-control-v1.sh")


class InstallerTest(unittest.TestCase):
    def test_unit_is_independent_of_app_and_has_no_ssh_or_caller_command(self):
        unit = subprocess.check_output(["/bin/bash", "-c", 'source "$1"; unit_content', "unit-test", str(SCRIPT)], text=True)
        self.assertIn("User=root\nGroup=root\n", unit)
        self.assertIn("ExecStart=/usr/local/libexec/atenea/release-control-v1.py\n", unit)
        self.assertIn("RuntimeDirectoryPreserve=yes\n", unit)
        self.assertIn("ProtectHome=read-only\nProtectSystem=strict\n", unit)
        self.assertIn("ReadWritePaths=/srv/atenea /run/atenea\n", unit)
        self.assertNotIn("/etc/atenea-worker",unit)
        self.assertNotIn("ssh", unit)
        self.assertNotIn("ExecStop=", unit)
        self.assertNotIn("Requires=atenea-backend", unit)
        source=SCRIPT.read_text()
        self.assertIn("--preflight-install",source)
        self.assertIn("systemctl restart atenea-release-control-v1.service",source)

    def test_ax42_unit_grants_only_its_installer_fixed_paths(self):
        unit=subprocess.check_output(["/bin/bash","-c",'source "$1"; unit_content AX42',"unit-test",str(SCRIPT)],text=True)
        self.assertIn("/usr/local/share/atenea",unit)
        self.assertIn("/etc/atenea-worker",unit)
        self.assertNotIn("/home/jose",unit)
        result=subprocess.run(["/bin/bash","-c",'source "$1"; unit_content FOREIGN',"unit-test",str(SCRIPT)],capture_output=True)
        self.assertEqual(2,result.returncode)
        self.assertEqual(b"",result.stdout)

    def test_foreign_operation_and_additional_arguments_rejected_before_preflight(self):
        for arguments in (("restart",), ("--command",), ("apply", "/foreign"), ("verify", "--execute"), ()):
            result = subprocess.run(["/bin/bash", str(SCRIPT), *arguments], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertNotIn("Root operator installation", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_netlink_is_allowed_only_for_the_ax42_fixed_installer(self):
        for mode, expected in (
            ("VPS", "AF_UNIX AF_INET AF_INET6"),
            ("AX42", "AF_UNIX AF_INET AF_INET6 AF_NETLINK"),
        ):
            with self.subTest(mode=mode):
                unit = subprocess.check_output([
                    "/bin/bash", "-c", 'source "$1"; unit_content "$2"',
                    "unit-test", str(SCRIPT), mode,
                ], text=True)
                restrictions = [line for line in unit.splitlines()
                                if line.startswith("RestrictAddressFamilies=")]
                self.assertEqual([f"RestrictAddressFamilies={expected}"], restrictions)
                for protection in (
                    "PrivateTmp=true", "ProtectHome=read-only", "ProtectSystem=strict",
                    "ProtectKernelTunables=true", "ProtectKernelModules=true",
                    "ProtectControlGroups=true", "UMask=0077",
                ):
                    self.assertIn(protection + "\n", unit)

    def test_bootstrap_only_adopts_and_never_installs_or_restarts_worker(self):
        source = SCRIPT.read_text()
        bootstrap = source.split("    bootstrap-platform)", 1)[1].split("      ;;", 1)[0]
        self.assertIn('"$PROGRAM" --bootstrap-platform', bootstrap)
        self.assertNotIn("systemctl", bootstrap)
        self.assertNotIn("install-agent-run-worker", bootstrap)
        self.assertNotIn(" apply", bootstrap)
        apply = source.split("    apply)",1)[1].split("      ;;",1)[0]
        self.assertEqual(1, apply.count('install -o root -g root -m 0755 "${SCRIPT_DIR}/release-control-v1.py" "$PROGRAM"'))


if __name__ == "__main__":
    unittest.main()
