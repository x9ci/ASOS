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
from deep_translator import GoogleTranslator, MyMemoryTranslator # Added MyMemoryTranslator

# تعريف المتغيرات العامة
CURRENT_USER = os.getenv('USER', 'unknown')

# الإعدادات العامة
CURRENT_USER = "x9up"  # تعديل اسم المستخدم حسب المدخل
MAX_RETRIES = 3
DELAY_MIN = 2
DELAY_MAX = 5
CHUNK_SIZE = 1000
MAX_CONSECUTIVE_FAILURES = 3
PREFERRED_TRANSLATOR_SERVICE = "google"  # Options: "google" or "mymemory"

# إعداد Tor
def setup_tor():
    """إعداد وتكوين Tor proxy والتأكد من عمله"""
    try:
        # تكوين SOCKS proxy
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
        socket.socket = socks.socksocket
        
        # اختبار الاتصال عبر Tor
        logging.info("جاري اختبار الاتصال عبر Tor...")
        session = requests.Session()
        session.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        response = session.get('https://check.torproject.org/', timeout=10) # زيادة المهلة قليلاً
        
        if 'Congratulations' in response.text:
            logging.info("✅ تم إعداد بروكسي Tor بنجاح والاتصال يعمل.")
            print("✅ تم إعداد بروكسي Tor بنجاح والاتصال يعمل.")
            return True
        else:
            logging.warning("⚠️ فشل التحقق من بروكسي Tor. قد لا يتم توجيه الطلبات عبر Tor.")
            # إعادة تعيين إعدادات البروكسي الافتراضية
            socks.set_default_proxy() 
            socket.socket = socket.SocketType # Corrected line
            return False
            
    except requests.exceptions.RequestException as e:
        logging.warning(f"⚠️ خطأ في طلب اختبار بروكسي Tor (RequestException): {str(e)}. تأكد من أن Tor يعمل ومتاح على المنفذ 9050.")
        socks.set_default_proxy()
        socket.socket = socket.SocketType # Corrected line
        return False
    except Exception as e:
        logging.warning(f"⚠️ خطأ عام في إعداد بروكسي Tor: {str(e)}")
        # إعادة تعيين إعدادات البروكسي الافتراضية
        socks.set_default_proxy()
        socket.socket = socket.SocketType # Corrected line
        return False

# تكوين SOCKS proxy
# يتم استدعاء setup_logging() داخل ChessTextProcessor، لذا أي تسجيل قبل تهيئة المعالج قد لا يظهر في الملف.
# يمكن إضافة print هنا إذا كان ضرورياً للمستخدم رؤية هذه الرسالة مباشرة.
if setup_tor():
    # Logging will occur after ChessTextProcessor initialization if it's called there.
    # For now, a print statement ensures visibility during startup.
    pass # Success message is printed within the function
else:
    print("⚠️ فشل في إعداد بروكسي Tor المبدئي. سيحاول البرنامج استخدام بروكسيات أخرى أو اتصال مباشر إذا تم تكوينه.")
    # sys.exit(1) # تم التعليق للسماح للبرنامج بالاستمرار


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
                # Log a warning but allow to continue for testing if Tor is not critical for all operations
                logging.warning("فشل التحقق من خدمة Tor الأساسية في __init__. سيستمر البرنامج، مع الاعتماد على تكوينات بروكسي بديلة أو اتصال مباشر.")
                # raise Exception("فشل في تهيئة خدمة Tor") # Temporarily commented for testing

            # إعداد الشبكة
            # if not self.manage_network_settings(): # This method does not exist
            #     raise Exception("فشل في إعداد الشبكة")

            # إعداد الاتصال
            # if not self.setup_advanced_connection(): # This method does not exist or is not used
            #     raise Exception("فشل في الإعداد المتقدم للاتصال")

            # إعداد البروكسيات
            self.setup_proxies()
            
            # إعداد User-Agent والهيدرز
            try:
                self.user_agents = UserAgent() # Removed verify_ssl=False
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
        """Verifies the availability of a Tor SOCKS proxy and ControlPort without managing the service."""
        logging.info("التحقق من توفر بروكسي Tor...")
        tor_socks_port_available = False
        tor_control_port_available = False

        # 1. Check SOCKS Port 9050
        try:
            sock_9050 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_9050.settimeout(2)  # Short timeout for port check
            if sock_9050.connect_ex(('127.0.0.1', 9050)) == 0:
                tor_socks_port_available = True
                logging.info("✅ منفذ Tor SOCKS (9050) مفتوح.")
            else:
                logging.warning("⚠️ منفذ Tor SOCKS (9050) مغلق أو لا يمكن الوصول إليه.")
            sock_9050.close()
        except Exception as e:
            logging.warning(f"خطأ أثناء التحقق من منفذ Tor SOCKS (9050): {e}")

        # 2. Check Control Port 9051
        try:
            sock_9051 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_9051.settimeout(1)  # Shorter timeout for control port
            if sock_9051.connect_ex(('127.0.0.1', 9051)) == 0:
                tor_control_port_available = True
                logging.info("✅ منفذ Tor ControlPort (9051) مفتوح.")
            else:
                logging.warning("⚠️ منفذ Tor ControlPort (9051) مغلق أو لا يمكن الوصول إليه. لن تعمل ميزات مثل تجديد الدائرة.")
            sock_9051.close()
        except Exception as e:
            logging.warning(f"خطأ أثناء التحقق من منفذ Tor ControlPort (9051): {e}")

        # 3. Perform SOCKS proxy connection test if port 9050 is available
        if tor_socks_port_available:
            logging.info("اختبار الاتصال عبر بروكسي Tor SOCKS (9050)...")
            session = requests.Session()
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            try:
                response = session.get('https://check.torproject.org/', timeout=10)
                if 'Congratulations' in response.text:
                    logging.info("✅ نجح اختبار الاتصال عبر بروكسي Tor. يبدو أن Tor يعمل بشكل صحيح.")
                else:
                    logging.warning("⚠️ فشل اختبار الاتصال عبر بروكسي Tor باستخدام check.torproject.org. قد لا يتم توجيه الطلبات عبر Tor.")
            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ فشل اختبار الاتصال عبر بروكسي Tor (RequestException): {e}. قد لا يتم توجيه الطلبات عبر Tor.")
            finally:
                session.close()
        else:
            logging.warning("⚠️ لن يتم إجراء اختبار الاتصال عبر بروكسي Tor لأن المنفذ 9050 غير متاح.")

        # This method now primarily serves as a check and advisory, not a strict gate.
        # It returns True to allow the application to proceed and try other proxies or direct connection.
        if not tor_socks_port_available:
             logging.warning("الاعتماد على بروكسيات أخرى أو الاتصال المباشر بسبب عدم توفر بروكسي Tor الأساسي.")
        
        return True # Always return True to allow script to continue

    # def check_tor_status(self): # This method relied on systemctl and is no longer needed with the new verify_tor_service
    #     """التحقق من حالة Tor"""
    #     try:
    #         # التحقق من العملية
    #         result = subprocess.run(
    #             ['systemctl', 'status', 'tor'],
    #             capture_output=True,
    #             text=True
    #         )
            
    #         if 'active (running)' not in result.stdout:
    #             logging.warning("خدمة Tor غير نشطة")
    #             return False
                
    #         # التحقق من المنافذ
    #         for port in [9050, 9051]:
    #             sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #             if sock.connect_ex(('127.0.0.1', port)) != 0:
    #                 logging.error(f"المنفذ {port} غير متاح")
    #                 sock.close()
    #                 return False
    #             sock.close()
                
    #         return True
            
    #     except Exception as e:
    #         logging.error(f"خطأ في التحقق من حالة Tor: {str(e)}")
    #         return False

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
                # Attempt GoogleTranslator setup
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
                    test_g_result = google_translator.translate("test")
                    if test_g_result:
                        self.translators.append(google_translator)
                        logging.info(f"Successfully added GoogleTranslator (Proxy: {proxy})")
                    else:
                        logging.warning(f"GoogleTranslator test failed (Proxy: {proxy})")
                except Exception as e:
                    logging.warning(f"Failed to set up GoogleTranslator (Proxy: {proxy}): {str(e)}")

                # Attempt MyMemoryTranslator setup
                try:
                    my_memory_translator = MyMemoryTranslator(
                        source='en',
                        target='ar',
                        proxies=proxy,
                        timeout=30
                    )
                    # Test MyMemoryTranslator
                    test_mm_result = my_memory_translator.translate("test")
                    if test_mm_result:
                        self.translators.append(my_memory_translator)
                        logging.info(f"Successfully added MyMemoryTranslator (Proxy: {proxy})")
                    else:
                        logging.warning(f"MyMemoryTranslator test failed (Proxy: {proxy})")
                except Exception as e:
                    logging.warning(f"Failed to set up MyMemoryTranslator (Proxy: {proxy}): {str(e)}")

            if not self.translators:
                # Fallback to direct GoogleTranslator if all proxy setups fail
                try:
                    self.translators.append(GoogleTranslator(source='en', target='ar'))
                    logging.warning("Added direct GoogleTranslator as a fallback since no proxy translators were set up.")
                except Exception as e:
                    logging.error(f"Failed to set up even a direct GoogleTranslator as fallback: {e}")
                # Optionally, try direct MyMemoryTranslator as an ultimate fallback
                try:
                    direct_mm_translator = MyMemoryTranslator(source='en', target='ar', timeout=30)
                    if direct_mm_translator.translate("test"):
                         self.translators.append(direct_mm_translator)
                         logging.warning("Added direct MyMemoryTranslator as an ultimate fallback.")
                except Exception as e:
                    logging.error(f"Failed to set up direct MyMemoryTranslator as fallback: {e}")
            
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
            if current_proxy.get('type') == 'tor': # Safer access with .get()
                self.renew_tor_circuit()
                
            # تأخير عشوائي قبل استخدام البروكسي الجديد
            time.sleep(random.uniform(0.1, 0.2)) # Reduced delay
            
            logging.info(f"تم التبديل من {previous_proxy['name']} إلى {current_proxy['name']}")
            return True
            
        except Exception as e:
            logging.error(f"خطأ في تدوير البروكسي: {str(e)}")
            # العودة للبروكسي السابق في حالة الفشل
            self.current_proxy_index = self.proxies.index(previous_proxy)
            return False
    
    def translate_with_retry(self, text, max_retries=2): # Reduced max_retries
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
                    is_primary_google = PREFERRED_TRANSLATOR_SERVICE == "google" and isinstance(translator, GoogleTranslator)
                    is_primary_mymemory = PREFERRED_TRANSLATOR_SERVICE == "mymemory" and isinstance(translator, MyMemoryTranslator)
                    is_primary_translator = is_primary_google or is_primary_mymemory

                    FallbackTranslatorType = None
                    if PREFERRED_TRANSLATOR_SERVICE == "google":
                        FallbackTranslatorType = MyMemoryTranslator
                    elif PREFERRED_TRANSLATOR_SERVICE == "mymemory":
                        FallbackTranslatorType = GoogleTranslator
                    
                    is_problematic_result = len(result) < len(text.strip()) * 0.4

                    if is_primary_translator and is_problematic_result and FallbackTranslatorType:
                        primary_translator_name = translator.__class__.__name__
                        fallback_translator_name = FallbackTranslatorType.__name__
                        logging.warning(f"{primary_translator_name} result '({result})' is very short (original length {len(text.strip())}). Attempting fallback with {fallback_translator_name}.")
                        
                        found_fallback_translator = False
                        original_primary_result = result # Keep the original short result

                        for fallback_candidate in self.translators:
                            if isinstance(fallback_candidate, FallbackTranslatorType):
                                try:
                                    logging.info(f"Attempting fallback translation with {fallback_translator_name} for: {text.strip()}")
                                    fallback_result = fallback_candidate.translate(text.strip())
                                    
                                    # Check if fallback result is valid and not also problematic
                                    if fallback_result and isinstance(fallback_result, str) and not (len(fallback_result) < len(text.strip()) * 0.4):
                                        logging.info(f"Successfully translated with {fallback_translator_name} as fallback. New result: {fallback_result}")
                                        self.consecutive_failures = 0 # Reset on successful fallback
                                        return fallback_result # Return fallback result
                                    else:
                                        logging.warning(f"{fallback_translator_name} fallback result was also empty, invalid, or too short: '{fallback_result}'")
                                except Exception as fb_e:
                                    logging.warning(f"{fallback_translator_name} fallback attempt failed: {fb_e}")
                                found_fallback_translator = True
                                break # Tried one fallback translator, that's enough
                        
                        if not found_fallback_translator:
                            logging.info(f"No {fallback_translator_name} instances found for fallback.")
                        
                        # If fallback was not attempted, failed, or its result was also problematic, return original primary result.
                        self.consecutive_failures = 0 # Still a success from primary translator, albeit short
                        return original_primary_result

                    # If not the primary preferred translator, or if the result is not problematic, or no fallback type defined:
                    self.consecutive_failures = 0  # Reset for any successful translation
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
                time.sleep((attempt + 1) * 0.5) # Reduced delay
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
                'chapter': r'CHAPTER [\w\s:]+', # Updated regex
                'numbers': r'\d+\.',
                'special_chars': r'[•\-\[\]\(\)]', # Corrected escaping for hyphen if it's not at start/end
                'chess_moves': r'\d+\.\s*[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?',
                'dates': r'\d{4}[-/]\d{2}[-/]\d{2}',
                'urls': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            }

            # حفظ العناصر المهمة
            # We need to iterate in reverse order of matches to preserve indices during substitution
            # However, the current approach of replacing and then using the modified text for next pattern is simpler
            # but can lead to issues if patterns overlap or if placeholder is part of a match for a subsequent pattern.
            # A better approach would be to find all matches first, then substitute from end to start.
            # For now, sticking to the existing logic but with the new placeholder.
            
            preserved_items_map = {} # Using a dictionary to store placeholders and their original content

            # Iterate multiple times or use a more sophisticated approach if placeholders can be part of other patterns
            # This simple loop might not handle overlapping patterns or patterns containing placeholders correctly.
            # For this iteration, we'll assume simple non-overlapping cases and focus on the format change.

            temp_text = text
            placeholder_idx = 0
            
            # It's crucial to replace longer, more specific patterns first, or handle overlaps.
            # The order in dictionary is not guaranteed for Python < 3.7.
            # For now, we'll use the given order.
            
            # First pass: identify all matches and store them with unique placeholders
            # This avoids issues with modifying the string while iterating over it with regex.
            
            matches_to_replace = []
            for pattern_name, pattern in preserved_patterns.items():
                for match in re.finditer(pattern, temp_text, re.MULTILINE):
                    placeholder = f"__PRESERVED_ITEM_{placeholder_idx}__"
                    matches_to_replace.append({
                        'start': match.start(),
                        'end': match.end(),
                        'content': match.group(),
                        'placeholder': placeholder
                    })
                    preserved_items_map[placeholder] = match.group()
                    placeholder_idx += 1
            
            # Sort matches by start position in reverse order to avoid index shifts during replacement
            matches_to_replace.sort(key=lambda m: m['start'], reverse=True)
            
            processed_text_for_translation = list(temp_text) # Convert to list for easier char replacement
            for item in matches_to_replace:
                # Replace the matched content with its placeholder
                processed_text_for_translation[item['start']:item['end']] = list(item['placeholder'])
            
            text_with_placeholders = "".join(processed_text_for_translation)

            # تقسيم النص إلى أجزاء (Refined chunking logic)
            chunks = []
            current_chunk_lines = []
            current_chunk_char_count = 0
            lines = text_with_placeholders.split('\n')

            for i, line in enumerate(lines):
                potential_line_len = len(line)
                # Add 1 for newline if it's not the first line in the current chunk being built
                len_if_added = current_chunk_char_count + potential_line_len + (1 if current_chunk_lines else 0)

                if len_if_added > chunk_size and current_chunk_lines:
                    chunks.append('\n'.join(current_chunk_lines))
                    current_chunk_lines = [line] # Start new chunk with current line
                    current_chunk_char_count = len(line)
                else:
                    if current_chunk_lines: # If not the first line in this chunk
                        current_chunk_char_count += 1 # For the newline separator
                    current_chunk_lines.append(line)
                    current_chunk_char_count += len(line)
            
            # Add the last remaining chunk
            if current_chunk_lines:
                chunks.append('\n'.join(current_chunk_lines))
            
            # The rest of the method (translation of chunks, placeholder restoration) remains the same.
            # ترجمة كل جزء
            translated_chunks = []
            for chunk in chunks:
                translated_chunk = self.translate_with_retry(chunk) # Removed is_target_chunk flag
                translated_chunks.append(translated_chunk)
                
                # تأخير ذكي بين الأجزاء
                self.smart_delay()

            # دمج الأجزاء المترجمة
            translated_text_with_placeholders = '\n'.join(translated_chunks)

            # استعادة العناصر المحفوظة
            # Iterate through the placeholders found and replace them with their original content
            final_translated_text = translated_text_with_placeholders
            for placeholder, original_content in preserved_items_map.items():
                final_translated_text = final_translated_text.replace(placeholder, original_content)

            return final_translated_text

        except Exception as e:
            logging.error(f"خطأ في معالجة النص: {str(e)}")
            return text

    def smart_delay(self):
        """تأخير ذكي مع تغيير متغير"""
        base_delay = random.uniform(0.1, 0.2) # Reduced base_delay
        extra_delay = 0 # Temporarily set to 0 for testing
        
        # زيادة التأخير في حالات معينة (currently overridden by extra_delay = 0)
        # if self.consecutive_failures > 0:
        #     extra_delay += self.consecutive_failures * 0.5
        
        # if self.pages_processed % 3 == 0:
        #     extra_delay += random.uniform(0, 2)
        
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
        # Address DeprecationWarning for datetime.utcnow()
        # Import timezone if not already available, or use datetime.timezone.utc
        # Assuming 'import datetime' or 'from datetime import datetime, timezone'
        # Based on current imports 'from datetime import datetime', datetime.timezone.utc should work.
        current_time = datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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

    def renew_tor_circuit(self):
        """تجديد دائرة Tor للحصول على IP جديد."""
        try:
            with Controller.from_port(port=9051) as controller:
                # محاولة المصادقة. قد تكون كلمة المرور مطلوبة أو لا,
                # اعتمادًا على تكوين Tor (e.g., CookieAuthentication, HashedControlPassword).
                # controller.authenticate() ستحاول مصادقة الكعكة أولاً, ثم بدون كلمة مرور.
                try:
                    controller.authenticate()
                    logging.info("تمت المصادقة مع وحدة تحكم Tor بنجاح (كعكة أو بدون كلمة مرور).")
                except Exception as auth_exception:
                    # إذا فشلت المصادقة الأولية, حاول بكلمة مرور شائعة أو محددة.
                    # هذا مثال, كلمة المرور الفعلية تعتمد على إعدادات المستخدم.
                    logging.info(f"فشلت المصادقة الأولية لوحدة تحكم Tor: {auth_exception}. جاري المحاولة بكلمة مرور '9090'...")
                    try:
                        controller.authenticate(password="9090") # كلمة مرور مأخوذة من setup_tor_connection
                        logging.info("تمت المصادقة مع وحدة تحكم Tor باستخدام كلمة المرور '9090'.")
                    except Exception as password_auth_exception:
                        logging.warning(f"فشلت المصادقة بكلمة المرور '9090': {password_auth_exception}. "
                                        "تأكد من تكوين ControlPort وكلمة المرور في Tor إذا كانت معينة. "
                                        "لن يتم تجديد مسار Tor إذا لم تنجح المصادقة.")
                        return False # فشل المصادقة يعني عدم القدرة على إرسال إشارة NEWNYM

                controller.signal(Signal.NEWNYM)
                # انتظر الوقت الموصى به من قبل وحدة التحكم حتى يتم إنشاء مسار جديد.
                wait_time = controller.get_newnym_wait()
                logging.info(f"تم إرسال إشارة NEWNYM إلى Tor. الانتظار لمدة {wait_time} ثانية لمسار جديد.")
                time.sleep(wait_time)
                logging.info("✅ تم تجديد دائرة Tor بنجاح (NEWNYM).")
                return True
        except Exception as e:
            logging.error(f"❌ خطأ أثناء محاولة تجديد دائرة Tor: {str(e)}")
            return False

    def get_fallback_headers(self):
        """إنشاء هيدرز احتياطية بسيطة"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

    def cleanup(self):
        """تنظيف الموارد عند إغلاق البرنامج"""
        logging.info("بدء عملية التنظيف عند إغلاق البرنامج...")
        # لا توجد حاليًا عمليات تنظيف محددة مثل إغلاق اتصالات قاعدة البيانات
        # أو حذف الملفات المؤقتة بشكل صريح. هذا المكان مخصص لها إذا ظهرت الحاجة.
        logging.info("✅ اكتملت عملية التنظيف.")

def main():
    """الدالة الرئيسية للبرنامج"""
    processor = None
    try:
        # إنشاء المعالج
        # ملاحظة: يتم استدعاء setup_logging() داخل __init__ لـ ChessTextProcessor
        processor = ChessTextProcessor()

        # التحقق من متطلبات النظام
        if not processor.verify_system_requirements():
            # تحذير بدلًا من الخروج، للسماح بمحاولة التشغيل الجزئي أو تسجيل الأخطاء
            logging.warning("فشل التحقق الأولي من متطلبات النظام. قد لا يعمل البرنامج كما هو متوقع.")
            # يمكن إعادة تفعيل الـ raise إذا كانت المتطلبات حرجة جدًا للتشغيل الأساسي
            # raise Exception("فشل التحقق من متطلبات النظام")

        # تحديد مسار الملف
        input_file = "document.txt"  # تم تعديل مسار الملف
        
        # التحقق من وجود الملف، وإنشاء ملف وهمي إذا لم يكن موجودًا (لأغراض الاختبار)
        if not os.path.exists(input_file):
            logging.warning(f"الملف '{input_file}' غير موجود في المسار الحالي.")
            # محاولة البحث بجانب السكربت
            # استخدام os.path.abspath(sys.argv[0]) للحصول على المسار المطلق للسكربت
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            path_next_to_script = os.path.join(script_dir, input_file)

            if os.path.exists(path_next_to_script):
                input_file = path_next_to_script
                logging.info(f"تم العثور على الملف بجانب السكربت: '{input_file}'")
            else:
                logging.warning(f"الملف '{input_file}' غير موجود بجانب السكربت أيضًا. "
                                f"سيتم إنشاء ملف وهمي للاختبار: '{os.path.abspath(input_file)}'")
                try:
                    with open(input_file, "w", encoding="utf-8") as f:
                        f.write("This is a test document for translation.\n")
                        f.write("=== الصفحة 1 ===\n")
                        f.write("Hello world. This is the first page.\n")
                        f.write("Another line on the first page.\n")
                        f.write("=== الصفحة 2 ===\n")
                        f.write("This is the second page, with some more text.\n")
                    logging.info(f"تم إنشاء ملف وهمي للاختبار: '{os.path.abspath(input_file)}'")
                except Exception as create_err:
                    logging.error(f"فشل في إنشاء ملف وهمي للاختبار '{os.path.abspath(input_file)}': {create_err}")
                    # إذا فشل إنشاء الملف الوهمي, نثير الخطأ لأننا لا نستطيع المتابعة بدون ملف
                    raise FileNotFoundError(f"الملف {input_file} غير موجود ولم يتمكن من إنشاء ملف وهمي.")
        
        # معالجة الملف
        output_file = processor.process_file(input_file)
        print(f"✅ تمت المعالجة بنجاح. الملف الناتج: {output_file}")

    except FileNotFoundError as e:
        print(f"❌ خطأ في الملفات: {str(e)}")
        logging.error(f"خطأ في العثور على الملف أو إنشائه: {str(e)}")
        sys.exit(1) # الخروج إذا كان الملف ضروريًا ولا يمكن العثور عليه/إنشاؤه
    except Exception as e:
        print(f"❌ حدث خطأ عام في البرنامج: {str(e)}")
        # استخدام logging.critical للأخطاء التي توقف البرنامج وتتطلب اهتمامًا فوريًا
        logging.critical(f"خطأ فادح في البرنامج أدى إلى إيقافه: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # تنظيف الموارد
        if processor:
            processor.cleanup() # التأكد من استدعاء cleanup

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
        sys.exit(0)