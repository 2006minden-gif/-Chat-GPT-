<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/vendor/tfpdf/font/unifont/ttfonts.php';
require_once dirname(__DIR__).'/vendor/tfpdf/tfpdf.php';
/** Pure PHP, offline, no shell, network, remote fonts, HTML or customer instructions. */
class NeuroDocumentPdf extends tFPDF {
 function Header(){ $this->Image(__DIR__.'/package/logo.png',18,10,12);$this->SetFont('DejaVu','B',12);$this->SetXY(34,11);$this->Cell(100,6,'НейроДело');$this->SetFont('DejaVu','',10);$this->SetXY(34,17);$this->Cell(100,6,'neurodelo.pro');$this->SetY(32); }
 function Footer(){ $this->SetY(-15);$this->SetFont('DejaVu','',10);$this->Cell(0,5,'Страница '.$this->PageNo().' / {nb}',0,0,'C'); }
}
function ct_pdf_bytes(string $title,array $paragraphs,bool $sample=false):string {
 $pdf=new NeuroDocumentPdf();$pdf->AddFont('DejaVu','','DejaVuSans.ttf',true);$pdf->AddFont('DejaVu','B','DejaVuSans-Bold.ttf',true);$pdf->SetMargins(18,32,18);$pdf->SetAutoPageBreak(true,22);$pdf->AliasNbPages();$pdf->AddPage();
 if($sample){$pdf->SetFont('DejaVu','B',14);$pdf->MultiCell(0,7,'Образец — не для подписания',0,'L');$pdf->Ln(4);}
 $pdf->SetFont('DejaVu','B',16);$pdf->MultiCell(0,8,$title,0,'L');$pdf->Ln(5);
 foreach($paragraphs as $p){$heading=(bool)preg_match('/^[0-9]+ [^\n]{1,100}$/u',$p);$pdf->SetFont('DejaVu',$heading?'B':'',13);if($heading&&$pdf->GetY()>247)$pdf->AddPage();$pdf->MultiCell(0,6.42,$p,0,'L');$pdf->Ln($heading?3:3.6);}
 $bytes=$pdf->Output('S');if(!str_starts_with($bytes,'%PDF-')||!str_contains($bytes,'/FontFile2'))throw new RuntimeException('pdf_font_embedding_failed');return $bytes;
}
