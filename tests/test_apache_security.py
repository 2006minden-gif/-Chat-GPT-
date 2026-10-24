"""Real Apache 2.4 regression: APACHE_BIN and APACHE_MODULE_DIR must be provided.
Uses only an isolated document root, synthetic files and a loopback listener.
"""
import http.client
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ApacheSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apache = os.environ['APACHE_BIN']
        modules = Path(os.environ['APACHE_MODULE_DIR'])
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.path = Path(cls.tmp.name)
        public = cls.path / 'public'
        shutil.copytree(ROOT / 'public', public)
        cls.backups = ['~.htaccess', 'index~.html', 'index.html~', '#index.html#',
                       'config.php.bak', 'config.php.BAK', 'index.old', 'index.orig',
                       'index.save', 'index.swp', 'index.swo', 'index.tmp',
                       'index.temp', 'index.backup', 'index.bkp', 'index.bak.1',
                       'config.bak.php', 'index.old.html', 'index.backup.zip', '.env']
        for name in cls.backups:
            (public / name).write_text('SYNTHETIC_PRIVATE_MARKER')
        (public / 'assets').mkdir()
        (public / 'assets/config.php.bak').write_text('SYNTHETIC_PRIVATE_MARKER')
        (public / 'allowed-backup-description.txt').write_text('PUBLIC_TEST_ASSET')
        sock = socket.socket(); sock.bind(('127.0.0.1', 0))
        cls.port = sock.getsockname()[1]; sock.close()
        config = cls.path / 'httpd.conf'
        config.write_text(f'''ServerRoot "{cls.path}"
ServerName localhost
Listen 127.0.0.1:{cls.port}
PidFile "{cls.path}/httpd.pid"
ErrorLog "{cls.path}/error.log"
LoadModule mpm_event_module "{modules}/mod_mpm_event.so"
LoadModule authz_core_module "{modules}/mod_authz_core.so"
LoadModule dir_module "{modules}/mod_dir.so"
DocumentRoot "{public}"
<Directory "{public}">
 AllowOverride All
 Require all granted
</Directory>
''')
        subprocess.run([cls.apache, '-t', '-f', str(config)], check=True, capture_output=True)
        cls.proc = subprocess.Popen([cls.apache, '-f', str(config), '-DFOREGROUND'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop)
        for _ in range(100):
            try:
                cls.request('/styles.css'); break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('Apache failed to start: ' + (cls.path / 'error.log').read_text())

    @classmethod
    def stop(cls):
        cls.proc.terminate(); cls.proc.wait(timeout=5)

    @classmethod
    def request(cls, path, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=3)
        connection.request(method, path)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_backups_denied_get_and_head(self):
        from urllib.parse import quote
        for name in self.backups + ['assets/config.php.bak', 'index.html', 'crm.html']:
            for method in ['GET', 'HEAD']:
                with self.subTest(name=name, method=method):
                    status, body = self.request('/' + quote(name), method)
                    self.assertEqual(status, 403)
                    self.assertNotIn(b'SYNTHETIC_PRIVATE_MARKER', body)
        self.assertEqual(self.request('/index%7E.html')[0], 403)
        self.assertEqual(self.request('/%7E.htaccess')[0], 403)

    def test_legitimate_assets_preserved(self):
        for name in ['styles.css', 'script.js', 'crm.css', 'crm.js', 'api-client.js', 'allowed-backup-description.txt']:
            with self.subTest(name=name):
                status, body = self.request('/' + name)
                self.assertEqual(status, 200)
                self.assertTrue(body)
        # PHP is deliberately not enabled in this static security fixture.
        # Application PHP execution is covered by test_prelaunch.py.
        self.assertNotEqual(self.request('/')[0], 500)

if __name__ == '__main__': unittest.main()
