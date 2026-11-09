"""Paper contract binds actual commercial state without pretending an online signature/decision."""
import json,secrets
import test_prospect_journey as prospects

class PaperAgreementFlow(prospects.ProspectJourney):
 def prepare(self):
  r=self.owner.post(self.base+'/api.php?r=crm/collab/projects/'+str(self.project_id)+'/documents',json={'request_key':secrets.token_hex(32),'kind':'specification','title':'SYNTHETIC owner brief','fields':{'title':'SYNTHETIC brief','requirements':'SYNTHETIC confirmed requirements for isolated test only','acceptance':'SYNTHETIC explicit acceptance criteria'},'file_ids':[]});rev=self.must(r)['revision'];r=self.owner.post(self.base+'/api.php?r=crm/collab/revisions/'+str(rev['id'])+'/ready',json={'request_key':secrets.token_hex(32),'version':int(rev['version'])});self.brief=self.must(r)['revision'];return super().prepare()
 def prepare_documents(self):
  oid,docs=super().prepare_documents();self.paper_docs=docs;self.must(self.fp(oid,'qualify'));self.must(self.fp(oid,'brief',revision_id=int(self.brief['id'])));qid=json.loads(docs[0]['input_snapshot'])['quotation']['id'];self.must(self.fp(oid,'quote',quotation_id=int(qid)));return oid,docs
 def create_link(self,oid,docs,mail=True,**extra):
  r=super().create_link(oid,docs,mail,**extra)
  if r.status_code==200 and self.fg(oid).json()['record']['commercial_state']=='PRICE_APPROVED':self.must(self.fp(oid,'proposal',binding_id=int(docs[0]['id'])))
  return r
 def bank(self,i,**extra):
  oid=int(i['order_id']);f=self.fg(oid).json()['record']
  if not f['agreement_binding_id']:
   k=secrets.token_hex(32);data={'binding_id':int(self.paper_docs[1]['id']),'version':int(f['version']),'confirm':True,'confirm_paper_acceptance':True,'reason':'SYNTHETIC owner reviewed real-test-fixture paper copy, no online client decision','request_key':k};r=self.must(self.fp(oid,'paper-agreement',**data));self.assertEqual(r['record']['commercial_state'],'PROPOSAL_ACCEPTED');self.assertEqual(r['record']['document_state'],'AGREED');self.assertTrue(self.must(self.fp(oid,'paper-agreement',**data))['action_replayed']);self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_lc_business_decisions WHERE order_id=? AND target_kind='PROPOSAL'",params=[oid])[0]['n'],0)
  return super().bank(i,**extra)
 def test_unverified_paper_cannot_skip_qualification_or_signature_review(self):
  oid,docs=self.prepare_documents();self.assertEqual(self.fp(oid,'paper-agreement',binding_id=int(docs[1]['id']),confirm_paper_acceptance=True).status_code,409);r=self.create_link(oid,docs,False);self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.fp(oid,'paper-agreement',binding_id=int(docs[1]['id']),confirm_paper_acceptance=True).status_code,422);self.assertEqual(self.fg(oid).json()['record']['commercial_state'],'PROPOSAL_SENT');self.assertIsNone(self.fg(oid).json()['record']['agreement_binding_id'])
