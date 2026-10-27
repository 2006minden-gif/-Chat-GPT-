"""Run the complete existing application suite after applying migration 004."""
import subprocess
import test_prelaunch as baseline

class MigratedPrelaunch(baseline.Prelaunch):
 @classmethod
 def setUpClass(cls):
  super().setUpClass()
  subprocess.run([cls.php,str(cls.path/'scripts/migrate.php'),'up'],check=True,capture_output=True,text=True)
