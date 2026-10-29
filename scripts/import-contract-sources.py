"""Rebuild private render catalog from the six supplied standalone DOCX sources.
Offline developer tool. Never reads completed documents, owner config or customer data.
"""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
FILES=[('01_contract.docx','agreement'),('02_specification.docx','specification'),('03_acceptance_act.docx','acceptance'),('04_change_agreement.docx','change_order'),('05_portfolio_permission.docx','portfolio_permission'),('06_review_permission.docx','review_permission')]
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def rebuild(root=ROOT):
 folder=root/'private/lifecycle/package';manifest=json.loads((root/'docs/CONTRACT-PACKAGE-MANIFEST.json').read_text())
 if manifest['customer_template_files']!=[n for n,k in FILES]:raise ValueError('source_allowlist_mismatch')
 items=[]
 for name,kind in FILES:
  path=folder/name
  with ZipFile(path) as z:
   info=z.getinfo('word/document.xml')
   if info.file_size>2_000_000:raise ValueError('source_too_large')
   x=ET.fromstring(z.read(info));body=x.find(W+'body');paragraphs=[]
   for p in body.iter(W+'p'):
    text=''.join((n.text or '') if n.tag==W+'t' else '\n' if n.tag==W+'br' else '\t' if n.tag==W+'tab' else '' for n in p.iter())
    if text.strip():paragraphs.append(text)
   if not paragraphs:raise ValueError('empty_source')
  items.append({'file':name,'kind':kind,'title':paragraphs[0],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'paragraphs':paragraphs[1:],'fields':sorted(set(re.findall(r'\{\{([^{}]+)\}\}','\n'.join(paragraphs))))})
 data={'schema_version':1,'status':'DRAFT_REQUIRES_OWNER_APPROVAL','templates':items}
 (folder/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 return data
if __name__=='__main__':rebuild()
