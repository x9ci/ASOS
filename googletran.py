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
from deep_translator import GoogleTranslator

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
        
        # تكوين SOCKS
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
        socket.socket = socks.socksocket
        
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

            # إعداد الشبكة
            if not self.manage_network_settings():
                raise Exception("فشل في إعداد الشبكة")

            # إعداد الاتصال
            if not self.setup_advanced_connection():
                raise Exception("فشل في الإعداد المتقدم للاتصال")

            # إعداد البروكسيات
            self.setup_proxies()
            
            # إعداد User-Agent والهيدرز
            try:
                self.user_agents = UserAgent(verify_ssl=False)
                self.headers = self.get_advanced_headers()
            except Exception as e:
                logging.warning(f"فشل في إعداد User-Agent المتقدم: {e}")
                self.headers = self.get_fallback_headers()

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

            # تكوين SOCKS
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            socket.socket = socks.socksocket

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
                try:
                    translator = GoogleTranslator(
                        source='en',
                        target='ar',
                        proxies=proxy,
                        timeout=30
                    )
                    
                    if hasattr(translator, 'session'):
                        # تكوين الجلسة
                        translator.session.verify = True
                        translator.session.trust_env = False
                        translator.session.headers.update(self.get_advanced_headers())
                        
                        # إعداد محاولات إعادة الاتصال
                        adapter = requests.adapters.HTTPAdapter(
                            pool_connections=5,
                            pool_maxsize=10,
                            max_retries=3,
                            pool_block=False
                        )
                        translator.session.mount('http://', adapter)
                        translator.session.mount('https://', adapter)
                    
                    # اختبار المترجم
                    test_result = translator.translate("test")
                    if test_result:
                        self.translators.append(translator)
                        logging.info(f"تم إضافة مترجم جديد (بروكسي: {proxy})")
                    
                except Exception as e:
                    logging.warning(f"فشل في إعداد المترجم مع البروكسي {proxy}: {str(e)}")
                    continue

            if not self.translators:
                # إضافة مترجم مباشر كحل أخير
                self.translators.append(GoogleTranslator(source='en', target='ar'))
                logging.warning("تم إعداد مترجم مباشر فقط")
            
            self.current_translator_index = 0
            logging.info(f"تم إعداد {len(self.translators)} مترجم بنجاح")

        except Exception as e:
            logging.error(f"خطأ في إعداد المترجمين: {str(e)}")
            # إعداد مترجم واحد للطوارئ
            self.translators = [GoogleTranslator(source='en', target='ar')]
            self.current_translator_index = 0

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
                self.renew_tor_circuit()
                
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
            for pattern_name, pattern in preserved_patterns.items():
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    preserved.append({
                        'start': match.start(),
                        'end': match.end(),
                        'content': match.group(),
                        'type': pattern_name,
                        'placeholder': f"[PRESERVED_{len(preserved)}]"
                    })
                    text = text[:match.start()] + f"[PRESERVED_{len(preserved)-1}]" + text[match.end():]

            # Part 2: Implement Space Insertion Around Placeholders Adjacent to Arabic Text
            # This is done after all placeholders are inserted and before chunking.
            ARABIC_UNICODE_RANGE = r'\u0600-\u06FF' # Standard Arabic Unicode range
            PLACEHOLDER_PATTERN = r'\[PRESERVED_\d+\]'

            # Case 1: Arabic char followed by placeholder, no space
            # Example: م[PRESERVED_0] -> م [PRESERVED_0]
            text = re.sub(rf"([{ARABIC_UNICODE_RANGE}])({PLACEHOLDER_PATTERN})", r"\1 \2", text)
            
            # Case 2: Placeholder followed by Arabic char, no space
            # Example: [PRESERVED_0]م -> [PRESERVED_0] م
            text = re.sub(rf"({PLACEHOLDER_PATTERN})([{ARABIC_UNICODE_RANGE}])", r"\1 \2", text)

            # تقسيم النص إلى أجزاء مع تحسينات للسياق - نسخة معدلة
            final_text_segments = [] # سيحتوي هذا على أجزاء نصية للترجمة وفواصل محفوظة

            # 1. تقسيم النص إلى فقرات مع الحفاظ على الفواصل
            paragraphs_and_para_separators = re.split(r'(\n\s*\n+)', text)

            for para_segment in paragraphs_and_para_separators:
                if not para_segment: # تجاهل الأجزاء الفارغة
                    continue
                
                # التحقق مما إذا كان الجزء هو فاصل فقرات
                if re.fullmatch(r'\n\s*\n+', para_segment):
                    final_text_segments.append(para_segment) # حفظ فاصل الفقرات
                    continue

                # إذا لم يكن فاصل فقرات، فهو نص فقرة يحتاج إلى مزيد من المعالجة
                paragraph_text = para_segment
                
                # 2. تقسيم الفقرات إلى جمل مع الحفاظ على الفواصل بين الجمل
                #    نستخدم lookahead سلبي (?![^\[]*\]) لتجنب التقسيم داخل [PRESERVED_X]
                #    ونستخدم lookbehind إيجابي (?<=[.?!]) للتقسيم بعد علامات الترقيم
                #    المجموعة الخارجية (...) تلتقط الفاصل نفسه (علامة الترقيم + المسافة)
                sentences_and_sentence_delimiters = re.split(r'((?<=[.?!])\s+(?![^\[]*\]))', paragraph_text)

                for sentence_segment in sentences_and_sentence_delimiters:
                    if not sentence_segment: # تجاهل الأجزاء الفارغة
                        continue

                    # التحقق مما إذا كان الجزء هو فاصل جملة (مثل ". ")
                    if re.fullmatch(r'(?<=[.?!])\s+', sentence_segment):
                        final_text_segments.append(sentence_segment) # حفظ فاصل الجملة
                        continue
                    
                    # إذا لم يكن فاصل جملة، فهو نص جملة يحتاج إلى ترجمة أو تقسيم إضافي
                    sentence_text_content = sentence_segment.strip() # إزالة أي مسافات بيضاء طرفية قد تكون متبقية
                    if not sentence_text_content: # إذا كان فارغًا بعد strip، تجاهله أو أضف المسافة الأصلية إذا كانت مهمة
                        if sentence_segment.isspace(): # إذا كان الجزء الأصلي مجرد مسافة
                             final_text_segments.append(sentence_segment)
                        continue


                    # 3. التعامل مع الجمل الطويلة (التي تتجاوز chunk_size)
                    if len(sentence_text_content) > chunk_size:
                        sub_segment_parts = []
                        current_sub_segment = ""
                        # تقسيم الجملة الطويلة إلى كلمات وفواصل للحفاظ على السلامة
                        words_and_spaces = re.split(r'(\s+)', sentence_text_content)

                        for part in words_and_spaces:
                            if len(current_sub_segment + part) > chunk_size and current_sub_segment:
                                sub_segment_parts.append(current_sub_segment)
                                current_sub_segment = part.lstrip() # ابدأ الجزء الجديد بالكلمة/الجزء بدون مسافة بادئة
                            else:
                                current_sub_segment += part
                        
                        if current_sub_segment: # إضافة أي جزء متبقي
                            sub_segment_parts.append(current_sub_segment)
                        
                        final_text_segments.extend(sub_segment_parts)
                    else:
                        # إضافة الجملة كما هي إذا كانت ضمن الحجم المطلوب
                        final_text_segments.append(sentence_text_content)
            
            # ترجمة الأجزاء النصية فقط
            translated_parts = []
            for i, segment_to_process in enumerate(final_text_segments):
                # التحقق مما إذا كان الجزء فاصلًا (فقرة أو جملة) أو مجرد مسافة بيضاء أو فارغ
                is_paragraph_separator = re.fullmatch(r'\n\s*\n+', segment_to_process)
                is_sentence_delimiter = re.fullmatch(r'(?<=[.?!])\s+', segment_to_process)
                is_whitespace_or_empty = not segment_to_process.strip()

                if is_paragraph_separator or is_sentence_delimiter or is_whitespace_or_empty:
                    translated_parts.append(segment_to_process) # الحفاظ على الفواصل والمسافات كما هي
                else:
                    # هذا جزء نصي يحتاج إلى ترجمة
                    logging.info(f"Translating segment ({i+1}/{len(final_text_segments)}): '{segment_to_process[:100]}...'")
                    translated_chunk = self.translate_with_retry(segment_to_process)
                    translated_parts.append(translated_chunk)
                    self.smart_delay() # تأخير ذكي بعد كل عملية ترجمة فعلية
            
            translated_text = "".join(translated_parts)

            # استعادة العناصر المحفوظة
            for item in preserved:
                translated_text = translated_text.replace(item['placeholder'], item['content'])
            
            # الخطوة الإضافية: تنظيف أي بقايا [preserved_d+] حرفية قد تظهر
            # translated_text = self.final_cleanup_of_leftover_placeholders(translated_text)
            # تم نقل هذا الاستدعاء إلى process_file ليعمل على الصفحة المترجمة بالكامل

            return translated_text

        except Exception as e:
            logging.error(f"خطأ في معالجة النص: {str(e)}")
            return text

    def final_cleanup_of_leftover_placeholders(self, text: str) -> str:
        """
        تنظيف نهائي لإزالة أي بقايا حرفية تشبه العناصر النائبة مثل [preserved_0]
        التي قد تظهر بشكل غير متوقع في النص المترجم.
        """
        # النمط للبحث عن: [preserved_رقم] (حرف p صغير، مع شرطة سفلية)
        # تم تحسينه ليشمل المسافات الاختيارية داخل الأقواس
        pattern = r'\[\s*preserved_\d+\s*\]'
        
        # البحث عن جميع التطابقات أولاً لأغراض التسجيل
        found_artifacts = re.findall(pattern, text)
        
        if found_artifacts:
            # تسجيل تحذير مع ذكر العناصر الفريدة التي تم العثور عليها
            unique_artifacts = sorted(list(set(found_artifacts)))
            logging.warning(
                f"تم العثور على بقايا عناصر نائبة حرفية في النص المترجم وجاري إزالتها: {', '.join(unique_artifacts)}"
            )
            
            # إزالة النمط واستبداله بمسافة واحدة للتعامل مع المسافات المحيطة
            # الخطوة 1: استبدل النمط والمسافات المحيطة به بمسافة واحدة
            text = re.sub(r'\s*' + pattern + r'\s*', ' ', text)
            
            # الخطوة 2: تطبيع المسافات المتعددة إلى مسافة واحدة
            text = re.sub(r'\s{2,}', ' ', text)
            
            # الخطوة 3: إزالة أي مسافات بادئة أو لاحقة من النص بأكمله
            text = text.strip()
            
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
                            translated_page_content = self.process_text_block(page)
                            
                            # تطبيق التنظيف النهائي على الصفحة المترجمة
                            cleaned_translated_page = self.final_cleanup_of_leftover_placeholders(translated_page_content)
                            
                            translated_pages.append(cleaned_translated_page)
                            
                            # كتابة الصفحة مباشرة إلى الملف
                            outfile.write(cleaned_translated_page + "\n")
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

        # تحديد مسار الملف (Hardcoded)
        input_file = "/home/dc/Public/fml/output/document.txt"
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
        # if processor:  # processor might not be initialized if argparse fails early
            # processor.cleanup() # cleanup method does not exist

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
        sys.exit(0)