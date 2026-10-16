#!/usr/bin/env python3
"""Fixed actor contract plus real distinct-UID recovery on synthetic Git only."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import grp
import signal
import stat
from types import SimpleNamespace
import unittest
import uuid
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fixtures = load('editable_actor_fixtures', 'test-development-change-source-update-v1.py')
module = fixtures.mediator_module
runner = load('editable_actor_runner', 'project-codex-runner-v1.py')


class ActorContractTest(unittest.TestCase):
    def setUp(self):
        self.accounts = {
            'atenea-worker': SimpleNamespace(pw_uid=999, pw_gid=988),
            'jose': SimpleNamespace(pw_uid=1000, pw_gid=1000),
        }
        for target, name, effect in (
                (module.pwd, 'getpwnam', lambda name: self.accounts[name]),
                (module.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=988, gr_mem=['jose'])
                 if name == 'atenea' else self.fail('arbitrary group')),
                (module.os, 'geteuid', lambda: 999)):
            patch = mock.patch.object(target, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    def test_fixed_two_actor_contract_matches_the_actual_runner_command(self):
        self.assertEqual((frozenset((999, 1000)), 988), module.managed_editable_actor_ids())
        self.assertEqual(module.WORKSPACE_CONTROL_USER, runner.CHANGE_WORKSPACE_OWNER)
        self.assertEqual(module.WORKSPACE_RUNNER_USER, runner.WORKSPACE_RUNNER_USER)
        self.assertEqual(module.WORKSPACE_EDITABLE_GROUP, runner.WORKSPACE_EDITABLE_GROUP)
        command = runner.sandbox_command(
            {'kind': 'project-codex-v4', 'runnerUser': 'root', 'runnerGroup': 'root',
             'modelId': runner.CODEX_MODEL, 'reasoningEffort': 'high', 'threadId': None},
            Path('/synthetic/change/atenea'), Path('/synthetic/mirror.git'),
            Path('/synthetic/result/final.txt'), Path('/synthetic/result/resolv.conf'),
            Path('/synthetic/result/empty-instructions'), 'reviewed', str(uuid.uuid4()))
        self.assertIn('User=jose', command)
        self.assertIn('Group=atenea', command)
        self.assertIn('UMask=0007', command)
        self.assertNotIn('User=root', command)
        self.assertNotIn('Group=root', command)

    def test_unrelated_caller_root_alias_or_missing_account_is_rejected(self):
        with mock.patch.object(module.os, 'geteuid', return_value=1000):
            with self.assertRaises(module.ContractError):
                module.managed_editable_actor_ids()
        for account in (SimpleNamespace(pw_uid=0, pw_gid=988), SimpleNamespace(pw_uid=999, pw_gid=988)):
            with self.subTest(account=account):
                self.accounts['jose'] = account
                with self.assertRaises(module.ContractError):
                    module.managed_editable_actor_ids()
        self.accounts.pop('jose')
        with self.assertRaisesRegex(module.ContractError, 'unavailable'):
            module.managed_editable_actor_ids()

    def test_group_and_runner_membership_are_not_inferred_from_the_file(self):
        self.accounts['atenea-worker'] = SimpleNamespace(pw_uid=999, pw_gid=999)
        with self.assertRaises(module.ContractError):
            module.managed_editable_actor_ids()
        self.accounts['atenea-worker'] = SimpleNamespace(pw_uid=999, pw_gid=988)
        with mock.patch.object(module.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=988, gr_mem=[])):
            with self.assertRaises(module.ContractError):
                module.managed_editable_actor_ids()


@contextlib.contextmanager
def identity(uid, gid):
    """Only a root-owned disposable fixture changes effective process identity."""
    previous = (os.getresuid(), os.getresgid(), os.getgroups())
    os.setgroups([gid])
    os.setresgid(gid, gid, 0)
    os.setresuid(uid, uid, 0)
    try:
        yield
    finally:
        os.seteuid(0)
        os.setresgid(*previous[1])
        os.setgroups(previous[2])
        os.setresuid(*previous[0])


@unittest.skipUnless(os.geteuid() == 0, 'real distinct-UID fixture requires root; CI runs it explicitly')
class DistinctActorRecoveryTest(unittest.TestCase):
    def setUp(self):
        # Use existing nonprivileged accounts, never create or modify OS users.
        try:
            self.control = pwd.getpwnam(module.WORKSPACE_CONTROL_USER).pw_uid
            self.writer = pwd.getpwnam(module.WORKSPACE_RUNNER_USER).pw_uid
            self.group = grp.getgrnam(module.WORKSPACE_EDITABLE_GROUP).gr_gid
        except KeyError:
            # GitHub's disposable runner has no installed Atenea accounts.
            self.control = pwd.getpwnam('nobody').pw_uid
            self.writer = pwd.getpwnam('daemon').pw_uid
            self.group = grp.getgrnam('nogroup').gr_gid
        self.foreign = 65533
        self.assertGreater(self.control, 0)
        self.assertGreater(self.writer, 0)
        self.assertNotEqual(self.control, self.writer)
        self.fixture = fixtures.SourceUpdateTest('runTest')
        self.addCleanup(self.cleanup_fixture)
        with identity(self.control, self.group):
            self.fixture.setUp()
        accounts = {
            'atenea-worker': SimpleNamespace(pw_uid=self.control, pw_gid=self.group),
            'jose': SimpleNamespace(pw_uid=self.writer, pw_gid=self.group),
        }
        # Only account lookup/root locations are synthetic. lstat, file I/O,
        # Git, EUIDs, journals, retained trees, and ownership checks are real.
        for target, name, effect in (
                (module.pwd, 'getpwnam', lambda name: accounts[name]),
                (module.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=self.group, gr_mem=['jose']))):
            patch = mock.patch.object(target, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(self.fixture.mediator, '_editable_actor_ids',
                                  side_effect=lambda worktree: module.managed_editable_actor_ids())
        patch.start()
        self.addCleanup(patch.stop)

    def cleanup_fixture(self):
        # TearDown knows only its mkdtemp synthetic tree; no real workspace.
        self.fixture.tearDown()

    def prepare(self):
        fixture = self.fixture
        publish = fixture.mediator.publish

        def publish_runner_files(request):
            fixture.root.chmod(0o770)
            fixture.workspaces.chmod(0o770)
            fixture.worktree.chmod(0o2770)
            # Return to privileged test harness before switching actors; no
            # privileged operation is performed on the actual managed tree.
            os.seteuid(0)
            try:
                with identity(self.writer, self.group):
                    # Existing drafts can have 0664. Future sandbox writes use
                    # the fixed shared/private umask from the actual command.
                    previous_mask = os.umask(0o007)
                    try:
                        self.write_as_runner('ticket.txt', 'ticket change\n')
                        (fixture.worktree / 'new-tests').mkdir()
                        (fixture.worktree / 'new-tests/HealthTest.kt').write_text('legitimate new test\n')
                    finally:
                        os.umask(previous_mask)
            finally:
                os.setresgid(self.group, self.group, 0)
                os.setresuid(self.control, self.control, 0)
            observed = fixture.mediator.execute(fixture.request('INSPECT'), 'INSPECT')
            request['sourceFingerprintSha256'] = observed['sourceFingerprintSha256']
            request.update(fixture.exact(request))
            return publish(request)

        with identity(self.control, self.group), mock.patch.object(fixture.mediator, 'publish', side_effect=publish_runner_files):
            request = fixture.prepare_fixture(stale_mirror=True)
        self.assertEqual(self.writer, (fixture.worktree/'ticket.txt').stat().st_uid)
        self.assertEqual(self.writer, (fixture.worktree/'new-tests').stat().st_uid)
        self.assertEqual(self.writer, (fixture.worktree/'new-tests/HealthTest.kt').stat().st_uid)
        self.assertEqual(0o660, stat.S_IMODE((fixture.worktree/'new-tests/HealthTest.kt').stat().st_mode))
        self.assertEqual(0o770, stat.S_IMODE((fixture.worktree/'new-tests').stat().st_mode) & 0o777)
        return request

    def write_as_runner(self, relative, content):
        path = self.fixture.worktree / relative
        if path.exists():
            path.unlink()
        path.write_text(content)
        path.chmod(0o664)

    def retain_prepared(self, request):
        with identity(self.control, self.group), mock.patch.object(self.fixture.mediator,
                '_resume_source_update', side_effect=module.ContractError('synthetic interruption')):
            with self.assertRaisesRegex(module.ContractError, 'synthetic interruption'):
                self.fixture.mediator.update_source(request, 'PREPARE')
        self.assertEqual('PREPARED', json.loads(self.fixture.path.read_bytes())['state'])

    def test_real_writer_then_worker_recovers_same_prepared_operation_and_finalizes_same_branch(self):
        fixture = self.fixture
        request = self.prepare()
        with identity(self.control, self.group):
            # Reproduce the former check, leaving exactly PREPARED and no
            # changed worktree bytes, just like the retained real operation.
            with mock.patch.object(fixture.mediator, '_editable_actor_ids', return_value=(frozenset((self.control,)), self.group)):
                with self.assertRaises(module.ContractError):
                    fixture.mediator.update_source(request, 'PREPARE')
            retained = json.loads(fixture.path.read_bytes())
            self.assertEqual('PREPARED', retained['state'])
            self.assertEqual('', fixture._git('-C', str(fixture.worktree), 'status', '--porcelain', capture=True))
            recovered = fixture.mediator.update_source(fixture.exact(request, operation='RECOVER', effect='RESUME_PINNED_SOURCE'), 'RECOVER')
            self.assertEqual('NEEDS_RESOLUTION', recovered['state'])
            self.assertEqual(request['operationId'], recovered['operationId'])
            self.assertEqual(retained['preparedTreeSha'], recovered['preparedTreeSha'])
            self.assertEqual(retained['intentSha256'], json.loads(fixture.path.read_bytes())['intentSha256'])
            self.assertEqual(self.writer, (fixture.worktree/'ticket.txt').stat().st_uid)
            self.assertEqual(self.writer, (fixture.worktree/'new-tests/HealthTest.kt').stat().st_uid)
            self.assertEqual(self.control, fixture.path.stat().st_uid)
            self.assertEqual(0o600, stat.S_IMODE(fixture.path.stat().st_mode))
            fixture.assert_retained()
        with identity(self.writer, self.group):
            self.write_as_runner('README.md', 'ticket and main resolved by Codex\n')
        with identity(self.control, self.group):
            observed = fixture.mediator.execute(fixture.request('INSPECT'), 'INSPECT')
            final = fixture.exact({**request, 'protocolVersion': module.SOURCE_FINALIZATION_PROTOCOL,
                'operation': 'FINALIZE', 'effect': 'FINALIZE_VALIDATED_SOURCE',
                'operationId': str(uuid.uuid4()), 'idempotencyKey': str(uuid.uuid4()),
                'sourceRevision': request['sourceRevision']+2,
                'sourceFingerprintSha256': observed['sourceFingerprintSha256'],
                'preparationOperationId': request['operationId'],
                'preparationReceiptSha256': recovered['receiptSha256'], 'validationProjectionSha256': 'f'*64})
            result = fixture.mediator.finalize_source(final, 'FINALIZE')
            self.assertEqual('PUBLISHED', result['state'])
            self.assertEqual('', fixture._git('-C', str(fixture.worktree), 'status', '--porcelain', capture=True))
            self.assertEqual(result['publishedHeadSha'], fixture._git(f'--git-dir={fixture.remote}',
                'rev-parse', request['workspaceBranch'], capture=True).strip())
            self.assertEqual(fixture.owner, (fixture.path.parent/'workspace-v1.json').read_bytes())
            self.assertEqual(fixture.publication, (fixture.path.parent/'branch-publication-v1.json').read_bytes())
            print(json.dumps({'distinctUidRecovery':'PASS','controlUid':self.control,'runnerUid':self.writer,
                              'groupGid':self.group,'sameOperationAndBranch':True}), flush=True)

    def test_foreign_user_group_and_private_journal_never_become_editable_authority(self):
        request = self.prepare()
        self.retain_prepared(request)
        fixture = self.fixture
        path = fixture.worktree/'ticket.txt'
        for uid, gid, mode in ((self.foreign, self.group, 0o664), (self.writer, 0, 0o664),
                               (self.writer, self.group, 0o666), (self.writer, self.group, 0o4664)):
            with self.subTest(uid=uid, gid=gid, mode=mode):
                os.chown(path, uid, gid)
                path.chmod(mode)
                with identity(self.control, self.group), self.assertRaises(module.ContractError):
                    fixture.mediator.update_source(request, 'PREPARE')
                self.assertEqual('ticket change\n', path.read_text())
        os.chown(path, self.writer, self.group)
        path.chmod(0o664)
        journal = fixture.path.parent/'workspace-v1.json'
        os.chown(journal, self.writer, self.group)
        with identity(self.control, self.group), self.assertRaises(module.ContractError):
            fixture.mediator.update_source(request, 'PREPARE')

    def test_runner_owned_control_root_or_private_preparation_is_still_rejected(self):
        request = self.prepare()
        self.retain_prepared(request)
        fixture = self.fixture
        for path in (fixture.worktree, fixture.path.parent, fixture.path):
            with self.subTest(path=path.name):
                os.chown(path, self.writer, self.group)
                with identity(self.control, self.group), self.assertRaises(module.ContractError):
                    fixture.mediator.update_source(request, 'PREPARE')
                os.chown(path, self.control, self.group)

    def test_nested_directory_with_unrelated_owner_or_group_is_rejected(self):
        request = self.prepare()
        self.retain_prepared(request)
        path = self.fixture.worktree/'new-tests'
        for uid, gid, mode in ((self.foreign, self.group, 0o770), (self.writer, 0, 0o770),
                               (self.writer, self.group, 0o777)):
            with self.subTest(uid=uid, gid=gid, mode=mode):
                os.chown(path, uid, gid)
                path.chmod(mode)
                with identity(self.control, self.group), self.assertRaises(module.ContractError):
                    self.fixture.mediator.update_source(request, 'PREPARE')

    def test_runner_symlink_hardlink_extra_file_or_later_edit_is_rejected_without_losing_bytes(self):
        request = self.prepare()
        self.retain_prepared(request)
        fixture = self.fixture
        path = fixture.worktree/'ticket.txt'
        outside = fixture.root/'outside'
        outside.write_text('do not read or change\n')
        outside.chmod(0o644)
        with identity(self.writer, self.group):
            path.unlink()
            path.symlink_to(outside)
        with identity(self.control, self.group), self.assertRaises(module.ContractError):
            fixture.mediator.update_source(request, 'PREPARE')
        with identity(self.writer, self.group):
            path.unlink()
            self.write_as_runner('ticket.txt', 'ticket change\n')
            os.link(path, fixture.worktree/'second-link')
        with identity(self.control, self.group), self.assertRaises(module.ContractError):
            fixture.mediator.update_source(request, 'PREPARE')
        with identity(self.writer, self.group):
            (fixture.worktree/'second-link').unlink()
            self.write_as_runner('later.txt', 'unattributed extra file\n')
        with identity(self.control, self.group), self.assertRaises(module.ContractError):
            fixture.mediator.update_source(request, 'PREPARE')
        with identity(self.writer, self.group):
            (fixture.worktree/'later.txt').unlink()
            self.write_as_runner('ticket.txt', 'later deliberate edit\n')
        with identity(self.control, self.group), self.assertRaises(module.ContractError):
            fixture.mediator.update_source(request, 'PREPARE')
        self.assertEqual('later deliberate edit\n', path.read_text())
        self.assertEqual('do not read or change\n', outside.read_text())

    def test_fifo_swap_after_lstat_is_rejected_without_a_blocking_open(self):
        request = self.prepare()
        self.retain_prepared(request)
        fixture = self.fixture
        target = fixture.worktree/'ticket.txt'
        open_file = module.os.open
        swapped = False

        def swap(path, flags, *args, **kwargs):
            nonlocal swapped
            if Path(path) == target and not swapped:
                swapped = True
                target.unlink()
                os.mkfifo(target, 0o660)
            return open_file(path, flags, *args, **kwargs)

        def timeout(_signum, _frame):
            raise AssertionError('retained file inspection blocked on a substituted FIFO')

        previous = signal.signal(signal.SIGALRM, timeout)
        signal.alarm(5)
        try:
            with identity(self.control, self.group), mock.patch.object(module.os, 'open', side_effect=swap):
                with self.assertRaisesRegex(module.ContractError, 'changed during inspection'):
                    fixture.mediator.update_source(request, 'PREPARE')
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        self.assertTrue(swapped)
        self.assertEqual('PREPARED', json.loads(fixture.path.read_bytes())['state'])


if __name__ == '__main__':
    unittest.main()
