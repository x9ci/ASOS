import sys
import os
import logging
import subprocess
import platform
import psutil
from datetime import datetime
import socket
import requests
import socks  # استخدام socks بدلاً من PySocks
from stem import Signal
from stem.control import Controller
import time
import random
from fake_useragent import UserAgent
import arabic_reshaper
from bidi.algorithm import get_display  # استخدام bidi بدلاً من python-bidi
import re
import json
from deep_translator import GoogleTranslator, MyMemoryTranslator

# تعريف المتغيرات العامة
CURRENT_USER = os.getenv('USER', 'unknown')

# الإعدادات العامة
CURRENT_USER = "x9up"  # تعديل اسم المستخدم حسب المدخل
MAX_RETRIES = 3
DELAY_MIN = 2
DELAY_MAX = 5
CHUNK_SIZE = 1000
MAX_CONSECUTIVE_FAILURES = 3

# إعداد Tor
def setup_tor():
    """إعداد وتكوين Tor"""
    try:
        # تكوين ملف Tor
        tor_config = """
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
DataDirectory /var/lib/tor
RunAsDaemon 1
ExitNodes {us},{nl},{de},{fr},{gb}
StrictNodes 1
CircuitBuildTimeout 60
MaxCircuitDirtiness 600
NumEntryGuards 8
"""
        with open('/tmp/torrc', 'w') as f:
            f.write(tor_config)
        
        # نسخ الملف إلى المكان الصحيح
        subprocess.run(['sudo', 'cp', '/tmp/torrc', '/etc/tor/torrc'])
        subprocess.run(['sudo', 'chmod', '644', '/etc/tor/torrc'])
        
        # إعادة تشغيل Tor
        subprocess.run(['sudo', 'service', 'tor', 'restart'])
        time.sleep(5)
        
        # تكوين SOCKS - تم التعليق لتجنب التعارض المحتمل مع إعدادات بروكسي مكتبة requests
        # socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
        # socket.socket = socks.socksocket
        
        return True
    except Exception as e:
        print(f"خطأ في إعداد Tor: {str(e)}")
        return False

# تكوين SOCKS proxy
if setup_tor():
    print("✅ تم إعداد Tor بنجاح")
else:
    print("❌ فشل في إعداد Tor")
    sys.exit(1)


class ChessTextProcessor:
    def __init__(self):
        """تهيئة المعالج"""
        try:
            # تعيين المتغيرات الأساسية قبل setup_logging
            self.current_user = CURRENT_USER
            self.start_time = datetime.now()
            self.pages_processed = 0
            self.consecutive_failures = 0
            self.current_proxy_index = 0
            self.current_translator_index = 0

            # إعداد التسجيل
            self.setup_logging()
            logging.info("بدء تهيئة المعالج...")

            # التحقق من متطلبات النظام
            if not self.verify_system_requirements():
                raise Exception("فشل التحقق من متطلبات النظام")

            # التحقق من Tor
            if not self.verify_tor_service():
                raise Exception("فشل في تهيئة خدمة Tor")

            # إعداد البروكسيات
            self.setup_proxies()
            
            # إعداد User-Agent والهيدرز
            try:
                self.user_agents = UserAgent()
                self.headers = self.get_advanced_headers()
            except Exception as e:
                logging.warning(f"فشل في إعداد User-Agent المتقدم: {e}")
                self.headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive'
                }

            # إعداد المترجمين
            self.setup_translators()

            # إعداد ترميز النظام
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')

            logging.info("✅ تم إكمال تهيئة المعالج بنجاح")

        except Exception as e:
            logging.error(f"❌ فشل في تهيئة المعالج: {str(e)}")
            raise

    def setup_tor_connection(self):
        """إعداد اتصال Tor"""
        try:
            # إعادة تشغيل خدمة Tor
            subprocess.run(['sudo', 'service', 'tor', 'restart'], check=True)
            time.sleep(5)

            # تكوين SOCKS - تم التعليق لتجنب التعارض المحتمل مع إعدادات بروكسي مكتبة requests
            # socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            # socket.socket = socks.socksocket

            # التحقق من الاتصال
            test_socket = socket.socket()
            test_socket.settimeout(10)
            test_socket.connect(('check.torproject.org', 443))
            test_socket.close()

            with Controller.from_port(port=9051) as controller:
                try:
                    controller.authenticate(password="9090")
                except:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
                time.sleep(controller.get_newnym_wait())

            logging.info("✅ تم إعداد اتصال Tor بنجاح")
            return True

        except Exception as e:
            logging.error(f"خطأ في إعداد اتصال Tor: {str(e)}")
            return False

    
    
    def verify_tor_service(self):
        """التحقق من خدمة Tor وإعادة تشغيلها إذا لزم الأمر"""
        try:
            # التحقق من وجود المجلدات الضرورية
            required_dirs = ['/var/lib/tor', '/etc/tor', '/var/log/tor']
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    subprocess.run(['sudo', 'mkdir', '-p', dir_path], check=True)
                    subprocess.run(['sudo', 'chown', 'debian-tor:debian-tor', dir_path], check=True)
                    
            # التحقق من حالة الخدمة
            status = subprocess.run(['systemctl', 'is-active', 'tor'], 
                                  capture_output=True, 
                                  text=True).stdout.strip()
            
            if status != 'active':
                logging.info("خدمة Tor غير نشطة. جاري إعادة التشغيل...")
                subprocess.run(['sudo', 'systemctl', 'restart', 'tor'], check=True)
                time.sleep(5)
            
            # التحقق من المنافذ
            for port in [9050, 9051]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                if result != 0:
                    logging.error(f"المنفذ {port} غير متاح")
                    return False
            
            # اختبار الاتصال عبر Tor
            session = requests.Session()
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            
            response = session.get('https://check.torproject.org/', timeout=10)
            if 'Congratulations' in response.text:
                logging.info("✅ تم التحقق من خدمة Tor بنجاح")
                return True
            else:
                logging.error("❌ الاتصال ليس عبر شبكة Tor")
                return False
                
        except Exception as e:
            logging.error(f"خطأ في التحقق من خدمة Tor: {str(e)}")
            return False
    
    def check_tor_status(self):
        """التحقق من حالة Tor"""
        try:
            # التحقق من العملية
            result = subprocess.run(
                ['systemctl', 'status', 'tor'],
                capture_output=True,
                text=True
            )
            
            if 'active (running)' not in result.stdout:
                logging.warning("خدمة Tor غير نشطة")
                return False
                
            # التحقق من المنافذ
            for port in [9050, 9051]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if sock.connect_ex(('127.0.0.1', port)) != 0:
                    logging.error(f"المنفذ {port} غير متاح")
                    sock.close()
                    return False
                sock.close()
                
            return True
            
        except Exception as e:
            logging.error(f"خطأ في التحقق من حالة Tor: {str(e)}")
            return False

    def get_advanced_headers(self):
        """إنشاء هيدرز متقدمة"""
        browsers = {
            'chrome': ['96.0.4664.110', '97.0.4692.71', '98.0.4758.102'],
            'firefox': ['95.0.2', '96.0.1', '97.0'],
            'safari': ['14.1.2', '15.0', '15.1']
        }
        platforms = [
            'Windows NT 10.0; Win64; x64',
            'Macintosh; Intel Mac OS X 10_15_7',
            'X11; Linux x86_64'
        ]

        browser = random.choice(list(browsers.keys()))
        version = random.choice(browsers[browser])
        platform = random.choice(platforms)
        
        headers = {
            'User-Agent': f'Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) {browser.capitalize()}/{version}',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Sec-GPC': '1',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Forwarded-For': '',
            'X-Real-IP': ''
        }
        return headers
    
    
    def verify_system_requirements(self):
        """التحقق من متطلبات النظام والمكتبات"""
        try:
            # التحقق من إصدار Python
            python_version = sys.version_info
            if python_version < (3, 7):
                raise Exception(f"يتطلب Python 3.7 أو أحدث. الإصدار الحالي: {python_version.major}.{python_version.minor}")

            # التحقق من المكتبات المطلوبة
            required_packages = {
                'deep_translator': '1.8.0',
                'requests': '2.25.0',
                'fake_useragent': '0.1.11',
                'stem': '1.8.0',
                'socks': '1.7.1',  # تغيير من PySocks إلى socks
                'arabic_reshaper': '2.1.3',
                'bidi': '0.4.2',   # تغيير من python-bidi إلى bidi
                'psutil': '5.8.0'
            }

            missing_packages = []
            for package in required_packages:
                try:
                    # محاولة استيراد المكتبة مباشرة
                    __import__(package)
                    logging.info(f"✅ تم العثور على مكتبة {package}")
                except ImportError as e:
                    logging.error(f"❌ لم يتم العثور على مكتبة {package}: {str(e)}")
                    missing_packages.append(package)

            if missing_packages:
                logging.error(f"المكتبات المفقودة: {', '.join(missing_packages)}")
                return False

            # التحقق من وجود Tor
            tor_path = self.check_tor_installation()
            if not tor_path:
                logging.error("❌ Tor غير مثبت في النظام")
                return False

            # التحقق من الذاكرة المتاحة
            memory = psutil.virtual_memory()
            if memory.available < 500 * 1024 * 1024:  # 500 MB
                logging.error("❌ الذاكرة المتاحة غير كافية")
                return False

            logging.info("✅ تم التحقق من متطلبات النظام بنجاح")
            return True

        except Exception as e:
            logging.error(f"❌ فشل التحقق من متطلبات النظام: {str(e)}")
            return False
    
    def check_tor_installation(self):
        """التحقق من تثبيت Tor"""
        try:
            # محاولة العثور على مسار Tor
            tor_path = subprocess.run(
                ['which', 'tor'],
                capture_output=True,
                text=True
            ).stdout.strip()

            if not tor_path:
                return False

            # التحقق من الإصدار
            tor_version = subprocess.run(
                ['tor', '--version'],
                capture_output=True,
                text=True
            ).stdout

            if tor_version:
                logging.info(f"إصدار Tor: {tor_version.split()[2]}")
                return tor_path

            return False

        except Exception as e:
            logging.error(f"خطأ في التحقق من تثبيت Tor: {str(e)}")
            return False

    def check_system_resources(self):
        """التحقق من موارد النظام"""
        try:
            # التحقق من الذاكرة
            memory = psutil.virtual_memory()
            if memory.available < 500 * 1024 * 1024:  # 500 MB
                logging.warning(f"الذاكرة المتاحة منخفضة: {memory.available / 1024 / 1024:.2f} MB")
                return False

            # التحقق من المساحة
            disk = psutil.disk_usage('/')
            if disk.free < 1 * 1024 * 1024 * 1024:  # 1 GB
                logging.warning(f"المساحة المتاحة منخفضة: {disk.free / 1024 / 1024 / 1024:.2f} GB")
                return False

            # التحقق من استخدام CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                logging.warning(f"استخدام CPU مرتفع: {cpu_percent}%")
                return False

            logging.info(f"""
            موارد النظام:
            - الذاكرة المتاحة: {memory.available / 1024 / 1024:.2f} MB
            - المساحة المتاحة: {disk.free / 1024 / 1024 / 1024:.2f} GB
            - استخدام CPU: {cpu_percent}%
            """)

            return True

        except Exception as e:
            logging.error(f"خطأ في التحقق من موارد النظام: {str(e)}")
            return False

    def check_user_permissions(self):
        """التحقق من صلاحيات المستخدم"""
        try:
            # التحقق من وجود المجلدات الضرورية
            required_dirs = [
                '/var/log/tor',
                '/etc/tor',
                'logs'
            ]

            for directory in required_dirs:
                if not os.path.exists(directory):
                    try:
                        os.makedirs(directory, exist_ok=True)
                    except PermissionError:
                        logging.warning(f"لا توجد صلاحيات لإنشاء المجلد: {directory}")
                        return False

            # التحقق من إمكانية الكتابة
            test_file = 'logs/test_permissions.txt'
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception:
                logging.warning("لا توجد صلاحيات للكتابة في مجلد السجلات")
                return False

            return True

        except Exception as e:
            logging.error(f"خطأ في التحقق من الصلاحيات: {str(e)}")
            return False
    
    def get_system_info(self):
        """الحصول على معلومات النظام"""
        try:
            info = {
                'python_version': sys.version.split()[0],
                'platform': platform.platform(),
                'processor': platform.processor(),
                'memory': psutil.virtual_memory(),
                'disk': psutil.disk_usage('/'),
                'network': psutil.net_if_stats(),
                'user': os.getenv('USER'),
                'home': os.getenv('HOME'),
                'pid': os.getpid()
            }
            
            logging.info(f"""
            ===== معلومات النظام =====
            Python: {info['python_version']}
            النظام: {info['platform']}
            المعالج: {info['processor']}
            الذاكرة المتاحة: {info['memory'].available / 1024 / 1024:.2f} MB
            المساحة المتاحة: {info['disk'].free / 1024 / 1024 / 1024:.2f} GB
            المستخدم: {info['user']}
            PID: {info['pid']}
            ========================
            """)
            
            return info

        except Exception as e:
            logging.error(f"خطأ في جمع معلومات النظام: {str(e)}")
            return None
    
    def setup_translators(self):
        """إعداد المترجمين مع تحسينات الأمان"""
        try:
            # تعطيل IPv6
            requests.packages.urllib3.util.connection.HAS_IPV6 = False
            
            self.translators = []
            
            # إعداد قائمة البروكسيات المتنوعة
            proxy_configs = [
                {
                    'http': 'socks5h://127.0.0.1:9050',
                    'https': 'socks5h://127.0.0.1:9050'
                },
                {
                    'http': 'socks5h://127.0.0.1:9150',
                    'https': 'socks5h://127.0.0.1:9150'
                },
                None  # مترجم مباشر للطوارئ
            ]

            # إنشاء مترجم لكل تكوين بروكسي
            for proxy in proxy_configs:
                # محاولة تهيئة MyMemoryTranslator أولاً
                try:
                    mymemory_translator = MyMemoryTranslator(
                        source='en-US',  # استخدام كود لغة مدعوم
                        target='ar-SA', # استخدام كود لغة مدعوم للغة العربية
                        proxies=proxy,
                        timeout=30
                    )
                    
                    # MyMemoryTranslator لا يستخدم session بنفس طريقة GoogleTranslator
                    # ولكن يمكن تطبيق إعدادات مشابهة إذا كانت المكتبة تدعمها مباشرة
                    # أو عبر تعديل الطلبات إذا لزم الأمر (غير واضح من الوثائق الحالية)

                    # اختبار المترجم
                    test_result_mymemory = mymemory_translator.translate("test")
                    if test_result_mymemory:
                        self.translators.append(mymemory_translator)
                        logging.info(f"تم إضافة MyMemoryTranslator (بروكسي: {proxy})")
                    
                except Exception as e:
                    logging.warning(f"فشل في إعداد MyMemoryTranslator مع البروكسي {proxy}: {str(e)}")

                # محاولة تهيئة GoogleTranslator
                try:
                    google_translator = GoogleTranslator(
                        source='en',
                        target='ar',
                        proxies=proxy,
                        timeout=30
                    )
                    
                    if hasattr(google_translator, 'session'):
                        # تكوين الجلسة
                        google_translator.session.verify = True
                        google_translator.session.trust_env = False
                        google_translator.session.headers.update(self.get_advanced_headers())
                        
                        # إعداد محاولات إعادة الاتصال
                        adapter = requests.adapters.HTTPAdapter(
                            pool_connections=5,
                            pool_maxsize=10,
                            max_retries=3,
                            pool_block=False
                        )
                        google_translator.session.mount('http://', adapter)
                        google_translator.session.mount('https://', adapter)
                    
                    # اختبار المترجم
                    test_result_google = google_translator.translate("test")
                    if test_result_google:
                        self.translators.append(google_translator)
                        logging.info(f"تم إضافة GoogleTranslator (بروكسي: {proxy})")
                    
                except Exception as e:
                    logging.warning(f"فشل في إعداد GoogleTranslator مع البروكسي {proxy}: {str(e)}")
                    continue

            if not self.translators:
                # إضافة مترجم Google مباشر كحل أخير إذا فشلت كل المحاولات الأخرى
                try:
                    self.translators.append(GoogleTranslator(source='en', target='ar'))
                    logging.warning("تم إعداد GoogleTranslator مباشر فقط كحل أخير")
                except Exception as e:
                    logging.error(f"فشل تام في إعداد أي مترجم: {str(e)}")
                    # يمكن رفع استثناء هنا إذا كان وجود مترجم ضروريًا لعمل البرنامج
            
            self.current_translator_index = 0
            if self.translators:
                logging.info(f"تم إعداد {len(self.translators)} مترجم بنجاح. المترجم الأساسي: {self.translators[0].__class__.__name__}")
            else:
                logging.error("لم يتم إعداد أي مترجم.")
                # قد تحتاج إلى معالجة هذا السيناريو بشكل مناسب

        except Exception as e:
            logging.error(f"خطأ كارثي في إعداد المترجمين: {str(e)}")
            # إعداد مترجم واحد للطوارئ إذا فشل كل شيء آخر
            try:
                self.translators = [GoogleTranslator(source='en', target='ar')]
                self.current_translator_index = 0
                logging.warning("تم إعداد GoogleTranslator مباشر كحل طوارئ أخير.")
            except Exception as final_e:
                logging.error(f"فشل حتى في إعداد مترجم الطوارئ: {final_e}")
                self.translators = [] # لا يوجد مترجمين متاحين
                # يجب التعامل مع هذا الوضع في الأجزاء الأخرى من الكود

    def setup_logging(self):
        """إعداد التسجيل مع تنسيق متقدم"""
        try:
            # إنشاء مجلد للسجلات إذا لم يكن موجوداً
            log_dir = 'logs'
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # إنشاء اسم الملف بالتاريخ
            log_filename = os.path.join(
                log_dir,
                f'translation_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            )

            # إعداد التسجيل الأساسي
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                handlers=[
                    logging.FileHandler(log_filename, encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ]
            )

            # إعداد سجل خاص للأخطاء
            error_handler = logging.FileHandler(
                os.path.join(log_dir, 'errors.log'),
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s\nStack trace:\n%(stack_info)s\n'
            )
            error_handler.setFormatter(error_formatter)
            logging.getLogger('').addHandler(error_handler)

            # تسجيل بداية العملية
            logging.info(f"بدء التسجيل في: {log_filename}")
            logging.info(f"معرف المستخدم: {self.current_user}")
            logging.info(f"نظام التشغيل: {platform.system()} {platform.release()}")

            return True

        except Exception as e:
            print(f"خطأ في إعداد التسجيل: {str(e)}")
            return False
    
    def setup_proxies(self):
        """إعداد وإدارة البروكسيات"""
        try:
            self.proxies = []
            
            # إضافة بروكسيات متنوعة
            proxy_configs = [
                {
                    'url': 'socks5h://127.0.0.1:9050',
                    'name': 'Tor Primary',
                    'type': 'tor'
                },
                {
                    'url': 'socks5h://127.0.0.1:9150',
                    'name': 'Tor Browser',
                    'type': 'tor'
                }
            ]

            for config in proxy_configs:
                if self.test_proxy(config['url']):
                    self.proxies.append(config)
                    logging.info(f"تم إضافة بروكسي: {config['name']}")

            # إضافة اتصال مباشر كخيار أخير
            self.proxies.append({
                'url': None,
                'name': 'Direct Connection',
                'type': 'direct'
            })

            self.current_proxy_index = 0
            self.consecutive_failures = 0
            
            logging.info(f"تم إعداد {len(self.proxies)} بروكسي")
            
        except Exception as e:
            logging.error(f"خطأ في إعداد البروكسيات: {str(e)}")
            # إعداد اتصال مباشر كحل طوارئ
            self.proxies = [{
                'url': None,
                'name': 'Direct Connection',
                'type': 'direct'
            }]
            self.current_proxy_index = 0

    def test_proxy(self, proxy_url, timeout=10):
        """اختبار صلاحية البروكسي"""
        if not proxy_url:
            return True

        try:
            session = requests.Session()
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            session.headers.update(self.get_advanced_headers())

            # اختبار الاتصال
            response = session.get('https://api.ipify.org?format=json', timeout=timeout)
            if response.status_code == 200:
                logging.info(f"بروكسي {proxy_url} يعمل بنجاح")
                return True

        except Exception as e:
            logging.warning(f"فشل اختبار البروكسي {proxy_url}: {str(e)}")

        return False

    def rotate_proxy(self):
        """تدوير البروكسي مع التعامل مع الأخطاء"""
        previous_proxy = self.proxies[self.current_proxy_index]
        
        try:
            # تجربة البروكسي التالي
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            current_proxy = self.proxies[self.current_proxy_index]
            
            # إذا كان البروكسي من نوع Tor، نقوم بتجديد المسار
            if current_proxy['type'] == 'tor':
                if not self.renew_tor_circuit(): # استدعاء الدالة المحدثة
                    logging.warning(f"فشل في تجديد دائرة Tor لـ {current_proxy['name']}")
                
            # تأخير عشوائي قبل استخدام البروكسي الجديد
            time.sleep(random.uniform(1, 3))
            
            logging.info(f"تم التبديل من {previous_proxy['name']} إلى {current_proxy['name']}")
            return True
            
        except Exception as e:
            logging.error(f"خطأ في تدوير البروكسي: {str(e)}")
            # العودة للبروكسي السابق في حالة الفشل
            self.current_proxy_index = self.proxies.index(previous_proxy)
            return False
    
    def translate_with_retry(self, text, max_retries=5):
        """ترجمة النص مع معالجة متقدمة للأخطاء وتغيير المترجمين"""
        if not text or not text.strip():
            return text

        original_text = text
        last_error = None

        for attempt in range(max_retries):
            try:
                # تجديد اتصال Tor قبل كل محاولة
                if attempt > 0:
                    self.renew_tor_circuit()
                    time.sleep(2)  # انتظار بعد تجديد المسار

                # اختيار المترجم
                translator = self.translators[self.current_translator_index]
                
                # تحديث الجلسة والهيدرز
                if hasattr(translator, 'session'):
                    current_proxy = self.proxies[self.current_proxy_index]
                    if current_proxy['url']:
                        translator.session.proxies = {
                            'http': current_proxy['url'],
                            'https': current_proxy['url']
                        }
                    translator.session.headers.update(self.get_advanced_headers())
                    translator.session.headers['X-Attempt'] = str(attempt)

                # محاولة الترجمة
                result = translator.translate(text.strip())
                
                if result and isinstance(result, str):
                    self.consecutive_failures = 0  # إعادة تعيين عداد الفشل
                    return result

            except Exception as e:
                last_error = str(e)
                logging.warning(f"فشل المحاولة {attempt + 1}: {last_error}")
                
                # زيادة عداد الفشل
                self.consecutive_failures += 1
                
                # تدوير المترجم والبروكسي بعد عدد معين من المحاولات الفاشلة
                if self.consecutive_failures >= 3:
                    self.rotate_translator()
                    self.rotate_proxy()
                    self.consecutive_failures = 0
                
                # تأخير تصاعدي بين المحاولات
                time.sleep((attempt + 1) * 2)
                continue

        # إذا فشلت كل المحاولات، نسجل الخطأ ونعيد النص الأصلي
        logging.error(f"فشلت جميع محاولات الترجمة. آخر خطأ: {last_error}")
        return original_text

    def process_text_block(self, text, chunk_size=CHUNK_SIZE):
        """معالجة النص مع الحفاظ على العناصر المهمة"""
        if not text or not text.strip():
            return text

        try:
            # الأنماط التي يجب حفظها
            preserved_patterns = {
                'page_header': r'=== الصفحة \d+ ===',
                'chapter': r'CHAPTER \w+',
                'numbers': r'\d+\.',
                'special_chars': r'[•\-\[\]\(\)]',
                'chess_moves': r'\d+\.\s*[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?',
                'dates': r'\d{4}[-/]\d{2}[-/]\d{2}',
                'urls': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            }

            # حفظ العناصر المهمة
            preserved = []
            # Iterating patterns one by one. For each pattern, find all its matches.
            # Then, iterate these matches in reverse order to perform replacements.
            # This avoids index shifting issues for multiple matches of the SAME pattern.
            for pattern_name, pattern in preserved_patterns.items():
                matches_for_current_pattern = []
                for match in re.finditer(pattern, text, re.MULTILINE):
                    matches_for_current_pattern.append(match)
                
                # Iterate in reverse order of matches to preserve indices
                for match in reversed(matches_for_current_pattern):
                    placeholder = f"[P#{len(preserved)}#P]" # Using a more unique placeholder format
                    preserved.append({
                        'start': match.start(), # Original start, for reference, not directly used in this revised logic
                        'end': match.end(),     # Original end
                        'content': match.group(),
                        'type': pattern_name,
                        'placeholder': placeholder
                    })
                    text = text[:match.start()] + placeholder + text[match.end():]

            # تقسيم النص إلى أجزاء
            chunks = []
            current_chunk = []
            for line in text.split('\n'):
                if len(' '.join(current_chunk)) > chunk_size:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                current_chunk.append(line)
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))

            # ترجمة كل جزء
            translated_chunks = []
            for chunk in chunks:
                translated_chunk = self.translate_with_retry(chunk)
                translated_chunks.append(translated_chunk)
                
                # تأخير ذكي بين الأجزاء
                self.smart_delay()

            # دمج الأجزاء المترجمة
            translated_text = '\n'.join(translated_chunks)

            # استعادة العناصر المحفوظة
            # Restore in reverse order of preservation to handle nested-like structures correctly
            # if a placeholder's content accidentally creates another valid placeholder.
            for item in reversed(preserved):
                translated_text = translated_text.replace(item['placeholder'], item['content'])

            return translated_text

        except Exception as e:
            logging.error(f"خطأ في معالجة النص: {str(e)}")
            return text

    def smart_delay(self):
        """تأخير ذكي مع تغيير متغير"""
        base_delay = random.uniform(1.5, 3.5)
        extra_delay = 0
        
        # زيادة التأخير في حالات معينة
        if self.consecutive_failures > 0:
            extra_delay += self.consecutive_failures * 0.5
        
        if self.pages_processed % 3 == 0:
            extra_delay += random.uniform(0, 2)
        
        time.sleep(base_delay + extra_delay)
        
        # تحديث العداد وتدوير البروكسي إذا لزم الأمر
        self.pages_processed += 1
        if self.pages_processed % 5 == 0:
            self.rotate_proxy()
            self.headers = self.get_advanced_headers()

    def process_file(self, input_filename):
        """معالجة الملف مع تتبع كامل وإدارة الأخطاء"""
        try:
            # التحقق من وجود الملف
            if not os.path.exists(input_filename):
                raise FileNotFoundError(f"الملف غير موجود: {input_filename}")

            # قراءة الملف
            with open(input_filename, 'r', encoding='utf-8') as file:
                content = file.read()

            # إنشاء المعلومات الوصفية
            metadata = self.create_metadata()

            # تقسيم المحتوى إلى صفحات
            pages = re.split(r'(=== الصفحة \d+ ===)', content)
            total_pages = len([p for p in pages if p.strip()])
            translated_pages = []
            current_page = 1

            # إنشاء ملف الترجمة
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = os.path.join(
                os.path.dirname(input_filename),
                f"translated_{timestamp}.txt"
            )

            # كتابة المعلومات الوصفية
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                outfile.write(metadata)
                outfile.write("="*50 + "\n\n")

                # معالجة كل صفحة
                for i, page in enumerate(pages):
                    if page.strip():
                        try:
                            logging.info(f"معالجة الصفحة {current_page} من {total_pages}")
                            print(f"جاري معالجة الصفحة {current_page} من {total_pages}")

                            # ترجمة الصفحة
                            translated_page = self.process_text_block(page)
                            translated_pages.append(translated_page)
                            
                            # كتابة الصفحة مباشرة إلى الملف
                            outfile.write(translated_page + "\n")
                            outfile.flush()  # ضمان حفظ البيانات
                            
                            current_page += 1
                            
                            # تدوير البروكسي كل عدة صفحات
                            if current_page % 3 == 0:
                                self.rotate_proxy()
                                
                        except Exception as e:
                            logging.error(f"خطأ في معالجة الصفحة {current_page}: {str(e)}")
                            # في حالة الخطأ، نحفظ النص الأصلي
                            outfile.write(page + "\n")
                            outfile.flush()

                # كتابة معلومات المعالجة النهائية
                completion_info = self.create_completion_info(current_page - 1)
                outfile.write("\n" + completion_info)

            logging.info(f"تم حفظ الترجمة في: {output_filename}")
            print(f"✅ تم حفظ الترجمة في: {output_filename}")
            return output_filename

        except Exception as e:
            logging.error(f"خطأ في معالجة الملف: {str(e)}")
            raise

    def create_metadata(self):
        """إنشاء المعلومات الوصفية للملف"""
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        system_info = platform.uname()
        
        metadata = (
            f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}\n"
            f"Current User's Login: {self.current_user}\n"
            f"System Info: {system_info.system} {system_info.release}\n"
            f"Processing Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Translator Version: deep-translator\n"
            f"Proxy Configuration: {self.proxies[self.current_proxy_index]['name']}\n\n"
        )
        return metadata

    def create_completion_info(self, pages_processed):
        """إنشاء معلومات إكمال المعالجة"""
        return (
            f"\n{'='*50}\n"
            f"Processing Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Total Pages Processed: {pages_processed}\n"
            f"Translation Status: Complete\n"
            f"{'='*50}\n"
        )

def main():
    """الدالة الرئيسية للبرنامج"""
    processor = None
    try:
        # إنشاء المعالج
        processor = ChessTextProcessor()

        # التحقق من متطلبات النظام
        if not processor.verify_system_requirements():
            raise Exception("فشل التحقق من متطلبات النظام")

        # تحديد مسار الملف
        input_file = "test_data/output/document.txt" # Changed to relative path
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"الملف غير موجود: {input_file}")

        # معالجة الملف
        output_file = processor.process_file(input_file)
        print(f"✅ تمت المعالجة بنجاح. الملف الناتج: {output_file}")

    except FileNotFoundError as e:
        print(f"❌ خطأ: {str(e)}")
        logging.error(f"ملف غير موجود: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ حدث خطأ: {str(e)}")
        logging.error(f"خطأ: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # تنظيف الموارد
        if processor:
            # processor.cleanup() # التأكد من وجود هذه الدالة أو إزالتها إذا لم تكن معرفة
            pass


    def renew_tor_circuit(self):
        """تجديد دائرة Tor للحصول على IP جديد"""
        try:
            with Controller.from_port(port=9051) as controller:
                try:
                    # محاولة المصادقة بكلمة مرور إذا كانت معدادة
                    # عادةً ما تكون كلمة المرور هي "password" أو قيمة فارغة إذا لم يتم تعيينها
                    # يجب التحقق من تكوين Tor لمعرفة كلمة المرور الصحيحة أو إذا كانت مطلوبة
                    controller.authenticate() # أو controller.authenticate(password="YOUR_TOR_PASSWORD")
                except Exception as auth_error:
                    logging.warning(f"فشل المصادقة مع Tor ControlPort: {auth_error}. قد لا تكون كلمة المرور مطلوبة أو صحيحة.")
                
                controller.signal(Signal.NEWNYM)
                # انتظار قصير للسماح بتكوين الدائرة الجديدة
                time.sleep(controller.get_newnym_wait()) 
                logging.info("✅ تم تجديد دائرة Tor بنجاح (NEWNYM signal sent).")
                return True
        except Exception as e:
            logging.error(f"❌ خطأ أثناء تجديد دائرة Tor: {str(e)}")
            return False

    def cleanup(self):
        """تنظيف الموارد عند إغلاق البرنامج"""
        logging.info("بدء عملية التنظيف...")
        # يمكنك إضافة أي عمليات تنظيف أخرى هنا، مثل إغلاق الاتصالات أو حذف الملفات المؤقتة
        logging.info("✅ اكتملت عملية التنظيف.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
        sys.exit(0)