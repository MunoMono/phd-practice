import gzip
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESTORE_SCRIPT = REPO_ROOT / 'scripts' / 'restore-innovationdesign-isolated.sh'
VALIDATOR_SCRIPT = REPO_ROOT / 'scripts' / 'validate-isolated-corpus.sh'
RUNNER_SCRIPT = REPO_ROOT / 'scripts' / 'run-isolated-retrieval-validation.sh'


class IsolatedRestoreScriptTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ['bash', str(RESTORE_SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_dangerous_database_name_is_rejected_before_restore(self):
        result = self.run_script('--database', 'testamentary-traces', '--backup', '/missing/backup.sql.gz')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('refusing dangerous active or system database name', result.stderr)

    def test_missing_backup_path_fails_safely(self):
        result = self.run_script('--backup', '/missing/backup.sql.gz')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('backup file does not exist', result.stderr)

    def test_invalid_gzip_fails_before_database_creation(self):
        with tempfile.NamedTemporaryFile(suffix='.sql.gz') as temporary_file:
            temporary_file.write(b'not a gzip archive')
            temporary_file.flush()
            result = self.run_script('--backup', temporary_file.name)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('gzip integrity verification', result.stderr)

    def test_existing_target_is_explicitly_guarded(self):
        contents = RESTORE_SCRIPT.read_text()

        self.assertIn('isolated database already exists and will not be overwritten', contents)
        self.assertLess(contents.index('database_exists; then'), contents.index('CREATE DATABASE'))

    def test_validator_reports_mismatch_without_mutation(self):
        contents = VALIDATOR_SCRIPT.read_text()

        self.assertIn('baseline_match=no', contents)
        self.assertIn('no data was modified', contents)
        self.assertNotIn('UPDATE ', contents)
        self.assertNotIn('INSERT ', contents)

    def test_retrieval_runner_targets_database_explicitly(self):
        contents = RUNNER_SCRIPT.read_text()

        self.assertIn('-e "POSTGRES_DB=$TARGET_DATABASE"', contents)
        self.assertIn('--entrypoint python', contents)
        self.assertIn('--expansion <term>', contents)
        self.assertIn('source="researcher_supplied"', contents)