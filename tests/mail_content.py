"""Parse recipient-visible plain alternatives with the standard MIME parser."""
from email import policy
from email.parser import BytesParser
def mail_plain(raw):
 message=BytesParser(policy=policy.default).parsebytes(raw)
 part=message.get_body(preferencelist=('plain',)) if message.is_multipart() else message
 if part is None:raise AssertionError('SMTP message has no plain-text alternative')
 return part.get_content()
