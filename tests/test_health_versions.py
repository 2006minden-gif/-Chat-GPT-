"""Baseline checks use deployed routes; publication must prove the new contract."""
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.parse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/deploy'))
import health

class HealthVersions(unittest.TestCase):
 def opener(self,portfolio):
  self.seen=[]
  class Response(io.BytesIO):pass
  def open(request,timeout):
   parsed=urllib.parse.urlparse(request.full_url);path=parsed.path
   if parsed.query and 'r=' in parsed.query:path+='?r='+urllib.parse.parse_qs(parsed.query)['r'][0]
   self.seen.append(path);status=200;headers={'Content-Type':'text/html'};body='НейроДело'.encode()
   if path=='/' and portfolio:headers['X-Neurodelo-Site']='portfolio-only'
   elif path in health.DENIED_PATHS:status=403;body=b''
   elif path.endswith(('.css','.js')):headers['Content-Type']='text/css' if path.endswith('.css') else 'application/javascript';body=b'asset'
   elif path in ['/api.php?r=session','/portfolio-api.php?r=session']:
    status=401;headers['Content-Type']='application/json';body=json.dumps({'detail':'Login required'}).encode()
   elif path in health.RETIRED_PATHS:status=410
   response=Response(body);response.status=status;response.headers=headers;response.url=request.full_url;return response
  return open
 def test_legacy_baseline_does_not_request_not_yet_installed_api_or_business_modules(self):
  report=health.snapshot(opener=self.opener(False));self.assertTrue(report['ok'])
  self.assertIn('/api.php?r=session',self.seen)
  self.assertNotIn('/portfolio-api.php?r=session',self.seen)
  self.assertNotIn('/billing.php',self.seen);self.assertNotIn('/customer-api.php',self.seen)
 def test_portfolio_contract_requires_new_owner_api_and_retired_endpoints(self):
  report=health.snapshot(opener=self.opener(True),expected_site_mode='portfolio-only');self.assertTrue(report['ok'])
  self.assertIn('/portfolio-api.php?r=session',self.seen)
  for path in health.RETIRED_PATHS:self.assertEqual(report['checks'][path]['status'],410)
 def test_old_site_cannot_pass_post_deployment_verification(self):
  report=health.snapshot(opener=self.opener(False),expected_site_mode='portfolio-only')
  self.assertFalse(report['ok']);self.assertFalse(report['checks']['/']['portfolio_only'])
 def test_connection_failure_stops_without_more_requests(self):
  called=[]
  def broken(request,timeout):called.append(request.full_url);raise urllib.error.URLError('SYNTHETIC_PRIVATE_ERROR')
  report=health.snapshot(opener=broken);self.assertFalse(report['ok']);self.assertFalse(report['complete']);self.assertEqual(len(called),1)
  self.assertNotIn('SYNTHETIC_PRIVATE_ERROR',json.dumps(report))
