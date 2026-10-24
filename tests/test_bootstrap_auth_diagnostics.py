"""Ensure GitHub API errors are actionable without leaking credentials."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "github"))
import control


class BootstrapAPIDiagnosticsTests(unittest.TestCase):
    def test_redacted_status_classification(self):
        samples = [
            ("HTTP 401: Bad credentials token=super-secret", "HTTP 401, invalid_or_expired_token"),
            ("HTTP 403: Resource not accessible by personal access token", "HTTP 403, insufficient_permissions_or_policy"),
            ("HTTP 404: Not Found", "HTTP 404, not_found_or_not_authorized"),
            ("HTTP 422: Validation failed", "HTTP 422, invalid_request"),
            ("HTTP 429: API limit", "HTTP 429, rate_limited"),
            ("Connection refused password=super-secret", "HTTP unknown, transport_or_unclassified_failure"),
        ]
        for stderr, expected in samples:
            with self.subTest(stderr=stderr):
                with patch.object(control.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr=stderr, stdout="")):
                    with self.assertRaises(control.GitHubFailure) as caught:
                        control.api("GET", "repos/" + control.REPO)
                    message = str(caught.exception)
                    self.assertIn(expected, message)
                    self.assertNotIn("super-secret", message)
                    self.assertNotIn("Bad credentials", message)

    def test_optional_404_is_none_but_403_is_not(self):
        with patch.object(control.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="(HTTP 404)", stdout="")):
            self.assertIsNone(control.api("GET", "repos/" + control.REPO + "/actions/variables/MISSING", missing=True))
        with patch.object(control.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="(HTTP 403)", stdout="")):
            with self.assertRaises(control.GitHubFailure):
                control.api("GET", "repos/" + control.REPO + "/actions/variables/MISSING", missing=True)


    def test_direct_probe_classifies_http_without_leaking_secret(self):
        import urllib.error
        for code in (401,403,404):
            with self.subTest(code=code), patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("https://api.github.com",code,"secret_token",{},None)):
                self.assertEqual(control.safe_api_probe("secret_token"),"direct_http_"+str(code))
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("secret_token")):
            self.assertEqual(control.safe_api_probe("secret_token"),"direct_transport_failure")
        self.assertEqual(control.safe_api_probe(""),"missing_token")

    def test_unknown_gh_failure_includes_read_only_probe_category(self):
        with patch.object(control.subprocess,"run",return_value=SimpleNamespace(returncode=1,stderr="network failure secret_token",stdout="")), patch.object(control,"safe_api_probe",return_value="direct_http_401"):
            with self.assertRaises(control.GitHubFailure) as caught:
                control.api("GET","repos/"+control.REPO)
            self.assertIn("safe_probe=direct_http_401",str(caught.exception))
            self.assertNotIn("secret_token",str(caught.exception))


if __name__ == "__main__":
    unittest.main()
