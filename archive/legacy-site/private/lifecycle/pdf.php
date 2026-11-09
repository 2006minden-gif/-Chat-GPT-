<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/vendor/tfpdf/font/unifont/ttfonts.php';
require_once dirname(__DIR__).'/vendor/tfpdf/tfpdf.php';
/** Pure PHP, offline, no shell, network, remote fonts, HTML or customer instructions. */
class NeuroDocumentPdf extends tFPDF {
 public ?int $sourceCreatedAt=null;
 public bool $compact=true;
 protected function _putinfo(){if($this->sourceCreatedAt!==null)$this->CreationDate=$this->sourceCreatedAt;parent::_putinfo();}
 function Header(){ $this->Image(__DIR__.'/package/logo.png',18,10,12);$this->SetFont('DejaVu','B',$this->compact?11:12);$this->SetXY(34,11);$this->Cell(100,6,'НейроДело');$this->SetFont('DejaVu','',$this->compact?9:10);$this->SetXY(34,17);$this->Cell(100,6,'neurodelo.pro');$this->SetY($this->compact?27:32); }
 function Footer(){ $this->SetY(-15);$this->SetFont('DejaVu','',$this->compact?9:10);$this->Cell(0,5,'Страница '.$this->PageNo().' / {nb}',0,0,'C'); }
}
function ct_pdf_bytes(string $title,array $paragraphs,bool $sample=false,?int $sourceCreatedAt=null,bool $compact=true):string {
 $pdf=new NeuroDocumentPdf();$pdf->compact=$compact;$pdf->sourceCreatedAt=$sourceCreatedAt;$pdf->SetTitle($title,true);$pdf->AddFont('DejaVu','','DejaVuSans.ttf',true);$pdf->AddFont('DejaVu','B','DejaVuSans-Bold.ttf',true);$margin=$compact?16:18;$top=$compact?27:32;$bottom=$compact?18:22;$body=$compact?11:13;$line=$compact?5:6.42;$gap=$compact?1.8:3.6;$limit=297-$bottom;$pdf->SetMargins($margin,$top,$margin);$pdf->SetAutoPageBreak(true,$bottom);$pdf->AliasNbPages();$pdf->AddPage();
 if($sample){$pdf->SetFont('DejaVu','B',14);$pdf->MultiCell(0,7,'Образец — не для подписания',0,'L');$pdf->Ln(4);}
 $pdf->SetFont('DejaVu','B',$compact?14:16);$pdf->MultiCell(0,$compact?6.4:8,$title,0,'L');$pdf->Ln($compact?3:5);
 foreach($paragraphs as $index=>$p){if(in_array($p,['Исполнитель','Заказчик'],true)){$height=0;$pdf->SetFont('DejaVu','',$body);for($j=$index;$j<count($paragraphs);$j++){if($j>$index&&in_array($paragraphs[$j],['Исполнитель','Заказчик'],true))break;$h=0;foreach(explode("\n",$paragraphs[$j]) as $row)$h+=max(1,(int)ceil($pdf->GetStringWidth($row)/(210-2*$margin)))+1;$height+=$h*$line+$gap;if(str_starts_with($paragraphs[$j],'Подпись'))break;}if($height<=$limit-$top&&$pdf->GetY()+$height>$limit)$pdf->AddPage();}$signatures=(bool)preg_match('/^(?:10 Реквизиты|8 Утверждение|Исполнитель$|Заказчик$)/u',$p);if($signatures&&$pdf->GetY()>($compact?$limit-36:160))$pdf->AddPage();$heading=(bool)preg_match('/^[0-9]+ [^\n]{1,100}$/u',$p);$pdf->SetFont('DejaVu',$heading?'B':'',$body);if($heading&&$pdf->GetY()>($compact?$limit-16:247))$pdf->AddPage();$pdf->MultiCell(0,$line,$p,0,'L');$pdf->Ln($heading?($compact?2:3):$gap);}
 $bytes=$pdf->Output('S');if(!str_starts_with($bytes,'%PDF-')||!str_contains($bytes,'/FontFile2'))throw new RuntimeException('pdf_font_embedding_failed');return $bytes;
}
