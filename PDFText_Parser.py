import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime, UTC
import pdfplumber
import json
import re
import sys
import os
from tqdm import tqdm

class PDFTextParser:
    def __init__(self, input_file: str, config: Dict):
        self.input_file = Path(input_file)
        self.config = config
        self.pdf = None
        self.stats = {
            'start_time': datetime.now(UTC).isoformat(),
            'end_time': None,
            'total_pages': 0,
            'extracted_blocks': 0,
            'processed_pages': 0,
            'total_words': 0,
            'arabic_words': 0,
            'english_words': 0,
            'numbers': 0,
            'errors': [],
            'processing_time': 0
        }
        
        # إضافة معلومات النظام
        self.stats.update({
            'system_info': {
                'python_version': sys.version,
                'os_name': os.name,
                'platform': sys.platform,
                'username': os.getlogin(),
                'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown'
            }
        })
        
        self._setup_logging()
        self._initialize()

    def _setup_logging(self):
        """إعداد نظام التسجيل"""
        log_dir = Path(self.config['output_dir']) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f'pdf_parser_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _initialize(self):
        """تهيئة المعالج"""
        try:
            if not self.input_file.exists():
                raise FileNotFoundError(f"الملف غير موجود: {self.input_file}")
            
            if self.input_file.suffix.lower() != '.pdf':
                raise ValueError(f"الملف ليس بصيغة PDF: {self.input_file}")
            
            self.pdf = pdfplumber.open(self.input_file)
            self.stats['total_pages'] = len(self.pdf.pages)
            self.stats['file_info'] = {
                'name': self.input_file.name,
                'size_mb': round(self.input_file.stat().st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(self.input_file.stat().st_ctime, UTC).isoformat(),
                'modified': datetime.fromtimestamp(self.input_file.stat().st_mtime, UTC).isoformat()
            }
            
            logging.info(f"""
=== بدء معالجة PDF ===
الملف: {self.input_file.name}
الحجم: {self.stats['file_info']['size_mb']} MB
عدد الصفحات: {self.stats['total_pages']}
====================""")
            
        except Exception as e:
            self._log_error("خطأ في تهيئة المعالج", e)
            raise

    def _analyze_text(self, text: str) -> str:
        """تحليل نوع النص"""
        if self._is_arabic_text(text):
            return 'arabic'
        elif text.isascii() and text.replace(' ', '').isalpha():
            return 'english'
        elif text.replace('.', '').isdigit():
            return 'number'
        return 'mixed'

    def _is_arabic_text(self, text: str) -> bool:
        """التحقق من النص العربي"""
        arabic_ranges = [
            (0x0600, 0x06FF),  # Arabic
            (0x0750, 0x077F),  # Arabic Supplement
            (0x08A0, 0x08FF),  # Arabic Extended-A
            (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
            (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
        ]
        
        for char in text:
            code = ord(char)
            for start, end in arabic_ranges:
                if start <= code <= end:
                    return True
        return False

    def process(self) -> List[Dict]:
        """معالجة الملف مع تتبع التقدم"""
        blocks = []
        start_time = datetime.now(UTC)
        
        try:
            print("\nبدء معالجة الصفحات...")
            for page_num in tqdm(range(self.stats['total_pages']), desc="معالجة الصفحات"):
                page_blocks = self._process_page(self.pdf.pages[page_num], page_num)
                if page_blocks:
                    blocks.extend(page_blocks)
                    self.stats['extracted_blocks'] += len(page_blocks)
                self.stats['processed_pages'] += 1
            
            self.stats['processing_time'] = (datetime.now(UTC) - start_time).total_seconds()
            return blocks
            
        except Exception as e:
            self._log_error("خطأ في معالجة الملف", e)
            return []
        finally:
            self._cleanup()

    def _process_page(self, page, page_num: int) -> List[Dict]:
        """معالجة صفحة واحدة"""
        try:
            # استخراج النص كاملاً
            page_text = page.extract_text()
            if page_text:
                print(f"\nصفحة {page_num + 1}:")
                print("-" * 50)
                print(page_text)
                print("-" * 50)
            
            # استخراج الكلمات
            words = page.extract_words(
                keep_blank_chars=True,
                x_tolerance=3,
                y_tolerance=3,
                use_text_flow=True
            )
            
            blocks = []
            for word in words:
                if word['text'].strip():
                    text = word['text']
                    text_type = self._analyze_text(text)
                    
                    block = {
                        'text': text,
                        'page': page_num + 1,
                        'bbox': (word['x0'], word['top'], word['x1'], word['bottom']),
                        'line_num': word.get('line_num', 0),
                        'text_type': text_type
                    }
                    
                    self._update_stats(text_type)
                    blocks.append(block)
            
            return blocks
            
        except Exception as e:
            self._log_error(f"خطأ في معالجة الصفحة {page_num + 1}", e)
            return []

    def _update_stats(self, text_type: str):
        """تحديث الإحصائيات"""
        self.stats['total_words'] += 1
        if text_type == 'arabic':
            self.stats['arabic_words'] += 1
        elif text_type == 'english':
            self.stats['english_words'] += 1
        elif text_type == 'number':
            self.stats['numbers'] += 1

    def _cleanup(self):
        """تنظيف الموارد"""
        try:
            if self.pdf:
                self.pdf.close()
            
            self.stats['end_time'] = datetime.now(UTC).isoformat()
            self._save_results()
            
        except Exception as e:
            self._log_error("خطأ في تنظيف الموارد", e)

    def _save_results(self):
        """حفظ النتائج"""
        try:
            output_dir = Path(self.config['output_dir'])
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            
            # حفظ الإحصائيات
            stats_file = output_dir / f"{self.input_file.stem}_stats_{timestamp}.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            
            # حفظ النص المستخرج
            text_file = output_dir / f"{self.input_file.stem}_text_{timestamp}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                for page_num in range(self.stats['total_pages']):
                    text = self.pdf.pages[page_num].extract_text()
                    if text:
                        f.write(f"\n=== الصفحة {page_num + 1} ===\n")
                        f.write(text)
                        f.write("\n" + "=" * 50 + "\n")
            
            print(f"\nتم حفظ النتائج في المجلد: {output_dir}")
            print(f"- الإحصائيات: {stats_file.name}")
            print(f"- النص المستخرج: {text_file.name}")
            
            logging.info(f"""
=== نتائج المعالجة ===
عدد الصفحات: {self.stats['total_pages']}
الكتل المستخرجة: {self.stats['extracted_blocks']}
الكلمات العربية: {self.stats['arabic_words']}
الكلمات الإنجليزية: {self.stats['english_words']}
الأرقام: {self.stats['numbers']}
وقت المعالجة: {self.stats['processing_time']:.2f} ثانية
===================""")
            
        except Exception as e:
            self._log_error("خطأ في حفظ النتائج", e)

    def _log_error(self, message: str, error: Exception):
        """تسجيل الأخطاء"""
        error_info = {
            'message': message,
            'error_type': type(error).__name__,
            'error_details': str(error),
            'time': datetime.now(UTC).isoformat()
        }
        self.stats['errors'].append(error_info)
        logging.error(f"{message}: {str(error)}", exc_info=True)


def main():
    try:
        # طباعة معلومات البداية
        current_time = datetime.now(UTC)
        print(f"=== معالج PDF ===")
        print(f"التاريخ والوقت (UTC): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"المستخدم: {os.getlogin()}")
        print(f"نظام التشغيل: {sys.platform}")
        print(f"إصدار Python: {sys.version.split()[0]}")
        print("=" * 40)
        print()
        
        # إعداد المسارات
        base_dir = Path('/home/dc/Public/fml')
        input_file = base_dir / 'input/document.pdf'
        
        if not input_file.exists():
            raise FileNotFoundError(f"الملف غير موجود: {input_file}")
        
        config = {
            'output_dir': str(base_dir / 'output'),
            'cache_dir': str(base_dir / 'cache')
        }
        
        # إنشاء المجلدات المطلوبة
        for dir_path in [config['output_dir'], config['cache_dir']]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        print(f"معالجة الملف: {input_file}")
        print("=" * 40)
        
        # معالجة الملف
        parser = PDFTextParser(str(input_file), config)
        blocks = parser.process()
        
        print("\nملخص النتائج:")
        print(f"- تم استخراج {len(blocks)} كتلة نصية")
        print(f"- راجع المجلد {config['output_dir']} للحصول على النتائج الكاملة")
        
    except Exception as e:
        logging.error(f"خطأ: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()