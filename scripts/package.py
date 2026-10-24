"""Create a review/deployment archive; does not deploy or include live configuration."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
output=root/'dist/neurodelo-sweb.zip'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((root/'public').iterdir()):
        if p.is_file():z.write(p,'public_html/'+p.name)
    for name in ['app.php','customer-auth.php','customer-mail.php','config.example.php','.htaccess']:
        z.write(root/'private'/name,'private/'+name)
    for p in sorted((root/'database').rglob('*.sql')):
        z.write(p,p.relative_to(root))
    z.write(root/'README.md','INSTALL.md')
    z.write(root/'PRELAUNCH-REPORT.md','PRELAUNCH-REPORT.md')
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    assert 'private/config.php' not in z.namelist()
    assert not any('privacy-policy.txt' in name for name in z.namelist())
    for name in ['public_html/api-client.js','public_html/privacy.php','database/migrations/003_consent.sql']:
        assert name in z.namelist()
    print(f'Archive verified: {len(z.namelist())} files, no live credentials or synthetic policy.')
