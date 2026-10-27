"""Run every discovered unique unittest case once, including import failures.

Several legacy suites import their parent TestCase classes. unittest discovers
those imports again in every module. Deduplicate identical qualified case IDs;
never filter test names, statuses, roles or modules.
"""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))

def unique_suite(suite):
    seen=set();cases=[];collected=0
    def collect(node):
        nonlocal collected
        if isinstance(node,unittest.TestSuite):
            for child in node:collect(child)
        else:
            collected+=1
            identity=node.id()
            if identity not in seen:seen.add(identity);cases.append(node)
    collect(suite)
    return unittest.TestSuite(cases),collected,len(cases)

if __name__=='__main__':
    suite,collected,count=unique_suite(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py'))
    if count==0:raise SystemExit('No tests discovered')
    print(f'Executing all {count} unique test IDs ({collected-count} duplicate imports removed).',file=sys.stderr,flush=True)
    result=unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
