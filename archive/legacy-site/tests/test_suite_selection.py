import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('run_all_tests',Path(__file__).resolve().parents[1]/'scripts/run-tests.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class SuiteSelection(unittest.TestCase):
 def test_only_identical_ids_removed_and_failures_are_preserved(self):
  class First(unittest.TestCase):
   def test_a(self):pass
   def test_b(self):pass
  failure=unittest.loader._FailedTest('missing_module',ImportError('synthetic import failure'))
  nested=unittest.TestSuite([First('test_a'),unittest.TestSuite([First('test_a'),First('test_b')]),failure])
  suite,collected,count=runner.unique_suite(nested)
  self.assertEqual(collected,4);self.assertEqual(count,3);self.assertEqual({t.id() for t in suite},{First('test_a').id(),First('test_b').id(),failure.id()})
