from deep_translator import GoogleTranslator
import re
from datetime import datetime
import os
import time
import random
import requests
from fake_useragent import UserAgent
import logging
import arabic_reshaper
from bidi.algorithm import get_display
import sys
from termcolor import colored
import socks
import socket
from stem import Signal
from stem.control import Controller
 # الإعدادات العامة
CURRENT_USER = "xx9c"
MAX_RETRIES = 3
DELAY_MIN = 2
DELAY_MAX = 5
CHUNK_SIZE = 1000  # حجم الجزء الواحد للترجمة
MAX_CONSECUTIVE_FAILURES = 3  # عدد المحاولات الفاشلة المتتالية قبل التبديل


# تكوين SOCKS proxy
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
socket.socket = socks.socksocket

def renew_tor_connection():
    """تجديد اتصال Tor"""
    try:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            time.sleep(5)  # انتظار لتجديد المسار
            return True
    except Exception as e:
        logging.error(f"فشل تجديد اتصال Tor: {str(e)}")
        return False

class ChessTextProcessor:
    def __init__(self):
        """تهيئة المعالج"""
        self.setup_logging()
        self.pages_processed = 0
        self.current_user = CURRENT_USER
        
        try:
            self.user_agents = UserAgent()
            self.headers = self.get_headers()
        except:
            self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # تكوين قائمة المترجمين
        self.setup_translators()
        sys.stdout.reconfigure(encoding='utf-8')

    def setup_translators(self):
        """إعداد المترجمين مع بروكسيات متنوعة"""
        try:
            self.translators = [
                # مترجم مباشر (للطوارئ)
                GoogleTranslator(source='en', target='ar'),
                
                # مترجمون مع بروكسيات Tor متعددة
                GoogleTranslator(source='en', target='ar', proxies={
                    'http': 'socks5h://127.0.0.1:9050',
                    'https': 'socks5h://127.0.0.1:9050'
                }),
                GoogleTranslator(source='en', target='ar', proxies={
                    'http': 'socks5h://127.0.0.1:9150',
                    'https': 'socks5h://127.0.0.1:9150'
                }),
                
                # مترجمون مع بروكسيات HTTP
                GoogleTranslator(source='en', target='ar', proxies={
                    'http': 'http://127.0.0.1:8118',
                    'https': 'http://127.0.0.1:8118'
                })
            ]
            self.current_translator_index = 0
            self.verify_tor_connection()  # التحقق من اتصال Tor
            logging.info("تم إعداد المترجمين بنجاح")
        except Exception as e:
            logging.error(f"خطأ في إعداد المترجمين: {str(e)}")
            self.translators = [GoogleTranslator(source='en', target='ar')]
            self.current_translator_index = 0

    def verify_tor_connection(self):
        """التحقق من اتصال Tor"""
        try:
            import socket
            import socks
            
            # تهيئة SOCKS
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            socket.socket = socks.socksocket
            
            # محاولة الاتصال
            test_socket = socket.socket()
            test_socket.connect(('www.google.com', 80))
            test_socket.close()
            
            logging.info("تم التحقق من اتصال Tor بنجاح")
            return True
        except Exception as e:
            logging.error(f"فشل التحقق من اتصال Tor: {str(e)}")
            return False

    def print_arabic(self, text):
        """طباعة النص العربي بشكل صحيح في الترمنال"""
        try:
            # تشكيل النص العربي
            reshaped_text = arabic_reshaper.reshape(text)
            # تطبيق خوارزمية BIDI
            bidi_text = get_display(reshaped_text)
            # طباعة النص مع لون للتمييز
            print(colored(bidi_text, 'green'))
        except Exception as e:
            print(f"Error displaying Arabic text: {str(e)}")
            print(text)  # طباعة النص الأصلي كحل بديل

    
    def get_headers(self):
        """إنشاء هيدرز HTTP"""
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    
    def setup_logging(self):
        """إعداد التسجيل"""
        logging.basicConfig(
            filename='translation_log.txt',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def load_proxies(self):
        """تحميل قائمة البروكسيات المتقدمة"""
        return [
            None,  # اتصال مباشر
            'socks5h://127.0.0.1:9050',  # Tor proxy
            'socks5h://127.0.0.1:9051',  # Tor proxy alternate
            'socks5h://127.0.0.1:9150',  # Tor Browser
            # قائمة بروكسيات SOCKS5 موثوقة
            'socks5h://163.172.31.44:1080',
            'socks5h://51.15.242.202:1080',
            'socks5h://163.172.189.32:1080',
        ]

    def setup_tor_connection(self):
        """إعداد اتصال Tor"""
        try:
            from stem import Signal
            from stem.control import Controller
            with Controller.from_port(port=9051) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
                time.sleep(5)  # انتظار لتغيير المسار
            return True
        except:
            return False

    def get_random_user_agent(self):
        """إنشاء User-Agent عشوائي"""
        browsers = ['chrome', 'firefox', 'safari', 'opera']
        versions = {
            'chrome': ['96.0.4664.110', '97.0.4692.71', '98.0.4758.102'],
            'firefox': ['95.0.2', '96.0.1', '97.0'],
            'safari': ['14.1.2', '15.0', '15.1'],
            'opera': ['82.0.4227.43', '83.0.4254.27']
        }
        
        browser = random.choice(browsers)
        version = random.choice(versions[browser])
        
        platforms = [
            'Windows NT 10.0; Win64; x64',
            'Macintosh; Intel Mac OS X 10_15_7',
            'X11; Linux x86_64',
            'Windows NT 6.1; Win64; x64'
        ]
        
        return f"Mozilla/5.0 ({random.choice(platforms)}) AppleWebKit/537.36 (KHTML, like Gecko) {browser.capitalize()}/{version}"

    def rotate_proxy(self):
        """تدوير البروكسي مع تقنيات متقدمة لتجنب الاكتشاف"""
        try:
            # تغيير البروكسي
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            current_proxy = self.proxies[self.current_proxy_index]
            
            # تغيير User-Agent
            new_user_agent = self.get_random_user_agent()
            self.headers = {
                'User-Agent': new_user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # إذا كان البروكسي Tor، قم بتغيير المسار
            if 'socks5h://127.0.0.1' in str(current_proxy):
                self.setup_tor_connection()
            
            # تأخير عشوائي
            time.sleep(random.uniform(2, 5))
            
            if current_proxy:
                self.translator = GoogleTranslator(
                    source='en', 
                    target='ar',
                    proxies={'http': current_proxy, 'https': current_proxy}
                )
                
                # إضافة الهيدرز
                self.translator.session.headers.update(self.headers)
                
            return True
        except Exception as e:
            logging.warning(f"فشل في تغيير البروكسي: {str(e)}")
            self.translator = GoogleTranslator(source='en', target='ar')
            return False


    def smart_delay(self):
        """تأخير ذكي مع تغيير متغير"""
        base_delay = random.uniform(1.5, 3.5)
        extra_delay = random.uniform(0, 2) if self.pages_processed % 3 == 0 else 0
        time.sleep(base_delay + extra_delay)
        
        self.pages_processed += 1
        if self.pages_processed % 5 == 0:
            self.rotate_proxy()
            self.headers = {'User-Agent': self.user_agents.random}

    def translate_with_retry(self, text, max_retries=MAX_RETRIES):
        """ترجمة النص مع إعادة المحاولة والتعامل مع الأخطاء"""
        if not text.strip():
            return text

        # تجربة كل المترجمين المتاحة
        for translator_index in range(len(self.translators)):
            try:
                self.current_translator_index = translator_index
                translator = self.translators[self.current_translator_index]
                
                # تأخير عشوائي قبل الترجمة
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                
                result = translator.translate(text.strip())
                if result:
                    return result
                    
            except Exception as e:
                logging.warning(f"فشل المترجم {translator_index + 1}: {str(e)}")
                continue
        
        # إذا فشلت كل المحاولات، أرجع النص الأصلي
        logging.error("فشلت جميع محاولات الترجمة")
        return text


    def rotate_translator(self):
        """تدوير المترجم مع التحقق من الاتصال"""
        try:
            previous_index = self.current_translator_index
            self.current_translator_index = (self.current_translator_index + 1) % len(self.translators)
            
            # التحقق من المترجم الجديد
            if 'socks5h' in str(self.translators[self.current_translator_index].proxies):
                if not self.verify_tor_connection():
                    # العودة إلى المترجم المباشر إذا فشل Tor
                    self.current_translator_index = 0
            
            time.sleep(random.uniform(1, 3))
            logging.info(f"تم التبديل إلى المترجم رقم {self.current_translator_index + 1}")
            
        except Exception as e:
            logging.error(f"خطأ في تدوير المترجم: {str(e)}")
            self.current_translator_index = 0
    
    def process_text_block(self, text):
        """معالجة النص مع تحسين الأداء"""
        # النمط المحسن للحفاظ على العناصر
        preserved_patterns = {
            'page_header': r'=== الصفحة \d+ ===',
            'chapter': r'CHAPTER \w+',
            'numbers': r'\d+\.',
            'special_chars': r'[•\-\[\]\(\)]',
            'chess_moves': r'\d+\.\s*[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?'
        }

        # تقسيم النص إلى أجزاء أصغر للترجمة
        chunks = []
        current_chunk = []
        for line in text.split('\n'):
            if len(' '.join(current_chunk)) > 1000:  # تقسيم كل 1000 حرف
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
            current_chunk.append(line)
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        # ترجمة كل جزء
        translated_chunks = []
        for chunk in chunks:
            # حفظ العناصر الخاصة
            preserved = []
            for pattern_name, pattern in preserved_patterns.items():
                matches = re.finditer(pattern, chunk, re.MULTILINE)
                for match in matches:
                    preserved.append((match.start(), match.group(), pattern_name))
                    chunk = chunk[:match.start()] + f"[PRESERVED_{pattern_name}_{len(preserved)-1}]" + chunk[match.end():]

            # ترجمة النص
            translated_chunk = self.translate_with_retry(chunk)
            
            # استعادة العناصر المحفوظة
            for idx, (_, content, pattern_name) in enumerate(preserved):
                placeholder = f"[PRESERVED_{pattern_name}_{idx}]"
                translated_chunk = translated_chunk.replace(placeholder, content)
            
            translated_chunks.append(translated_chunk)
            self.smart_delay()  # تأخير ذكي بين الأجزاء

        return '\n'.join(translated_chunks)

    def process_file(self, input_filename):
        """معالجة الملف الكامل"""
        try:
            with open(input_filename, 'r', encoding='utf-8') as file:
                content = file.read()

            # تقسيم إلى صفحات
            pages = re.split(r'(=== الصفحة \d+ ===)', content)
            translated_pages = []

            for i, page in enumerate(pages):
                if page.strip():
                    logging.info(f"معالجة الصفحة {i + 1} من {len(pages)}")
                    translated_page = self.process_text_block(page)
                    translated_pages.append(translated_page)

            # إنشاء الملف المترجم
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{os.path.splitext(input_filename)[0]}_translated_{timestamp}.txt"
            
            header = f"Translation started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"{'='*50}\n\n"
            
            footer = f"\n{'='*50}\n"
            footer += f"Processing Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            footer += f"Total Pages Processed: {self.pages_processed}\n"
            footer += f"{'='*50}\n"

            with open(output_filename, 'w', encoding='utf-8') as file:
                file.write(header + ''.join(translated_pages) + footer)

            logging.info(f"تم حفظ الترجمة في: {output_filename}")
            print(f"تم حفظ الترجمة في: {output_filename}")

        except Exception as e:
            logging.error(f"خطأ في معالجة الملف: {str(e)}")
            print(f"حدث خطأ: {str(e)}")

        
def main():
    try:
        processor = ChessTextProcessor()
        input_file = "/home/dc/Public/fml/output/document.txt"
        processor.process_file(input_file)
    except Exception as e:
        logging.error(f"خطأ في البرنامج الرئيسي: {str(e)}")
        print(f"خطأ في البرنامج: {str(e)}")

if __name__ == "__main__":
    main()