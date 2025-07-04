import sys
import os
import logging
import subprocess
import platform
import psutil
from datetime import datetime, timezone
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

# تم إزالة دالة setup_tor العالمية والطباعة المصاحبة لها.
# يفترض الآن أن خدمة Tor مثبتة ومهيأة بشكل صحيح من قبل المستخدم.

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
            self.tor_enabled = True # قيمة افتراضية

            # إعداد التسجيل
            self.setup_logging()
            logging.info("بدء تهيئة المعالج...")

            # التحقق من متطلبات النظام
            if not self.verify_system_requirements():
                raise Exception("فشل التحقق من متطلبات النظام")

            # التحقق من Tor
            self.tor_enabled = self.verify_tor_service() # نحفظ حالة Tor
            if not self.tor_enabled:
                logging.warning("فشل في تهيئة خدمة Tor. سيتم محاولة المتابعة بدونه أو بالاعتماد على الاتصال المباشر إذا تم إعداده كخيار احتياطي.")
            # لم نعد نطلق استثناء هنا

            # تم إزالة الاستدعاءات للدوال غير المعرفة manage_network_settings و setup_advanced_connection
            # # إعداد الشبكة
            # if not self.manage_network_settings():
            #     raise Exception("فشل في إعداد الشبكة")

            # # إعداد الاتصال
            # if not self.setup_advanced_connection():
            #     raise Exception("فشل في الإعداد المتقدم للاتصال")

            # إعداد البروكسيات
            self.setup_proxies()
            
            # إعداد User-Agent والهيدرز
            try:
                self.user_agents = UserAgent()
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

    def request_new_tor_circuit(self):
        """محاولة طلب دائرة Tor جديدة عبر منفذ التحكم إذا كان متاحًا."""
        logging.info("محاولة طلب دائرة Tor جديدة (NEWNYM)...")
        # التحقق أولاً من توفر منفذ التحكم
        sock_9051_check = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_9051_check.settimeout(2) # مهلة قصيرة للتحقق
        control_port_available = sock_9051_check.connect_ex(('127.0.0.1', 9051)) == 0
        sock_9051_check.close()

        if not control_port_available:
            logging.warning("منفذ التحكم Tor (9051) غير متاح. لا يمكن طلب دائرة جديدة.")
            return False

        try:
            with Controller.from_port(port=9051) as controller:
                try:
                    # محاولة المصادقة بدون كلمة مرور أولاً (شائع في الإعدادات الافتراضية)
                    controller.authenticate()
                    logging.info("تمت المصادقة مع Tor Controller بنجاح (بدون كلمة مرور).")
                except Exception as auth_err_no_pass:
                    logging.info(f"فشلت المصادقة بدون كلمة مرور: {auth_err_no_pass}. محاولة بكلمة مرور افتراضية '9090' أو كلمة مرور cookie...")
                    try:
                        # محاولة بكلمة مرور شائعة أو الاعتماد على مصادقة cookie إذا كانت مفعلة
                        # إذا كان لديك كلمة مرور محددة، استخدمها هنا.
                        # controller.authenticate(password="YOUR_PASSWORD")
                        # أو الاعتماد على ملف cookie إذا كان Tor مهيأ لذلك
                        controller.authenticate() # إعادة المحاولة قد تعمل إذا كان هناك cookie
                    except Exception as auth_err_with_pass:
                        logging.warning(f"فشل المصادقة مع Tor Controller (مع محاولة كلمة مرور/cookie): {auth_err_with_pass}. قد لا يتمكن البرنامج من طلب دوائر Tor جديدة.")
                        return False # لا يمكن المتابعة بدون مصادقة ناجحة

                controller.signal(Signal.NEWNYM)
                wait_time = controller.get_newnym_wait()
                logging.info(f"تم إرسال إشارة NEWNYM إلى Tor. الانتظار لمدة {wait_time} ثانية...")
                time.sleep(wait_time)
                logging.info("✅ تم طلب دائرة Tor جديدة بنجاح.")
                return True
        except ConnectionRefusedError:
            logging.error("فشل الاتصال بمنفذ التحكم Tor (9051). تأكد من أن Tor يعمل وأن ControlPort مفعل ومتاح.")
            return False
        except Exception as e:
            logging.error(f"خطأ غير متوقع عند طلب دائرة Tor جديدة: {str(e)}")
            return False

    def verify_tor_service(self):
        """التحقق من أن خدمة Tor تعمل وتستمع على المنافذ المطلوبة."""
        logging.info("التحقق من خدمة Tor...")
        try:
            # التحقق من حالة الخدمة (بدون sudo)
            # هذا الأمر قد لا يعمل بدون صلاحيات كافية أو إذا لم تكن systemd هي نظام init
            # لذا، سنعتمد بشكل أساسي على اختبار الاتصال بالمنافذ
            try:
                status_output = subprocess.run(['systemctl', 'is-active', 'tor'],
                                     capture_output=True,
                                     text=True, check=False) # check=False لتجنب الخطأ
                status = status_output.stdout.strip()
                if status == 'active':
                    logging.info("systemctl: خدمة Tor نشطة.")
                else:
                    logging.warning(f"systemctl: خدمة Tor ليست نشطة (الحالة: {status}). stdout: {status_output.stdout}, stderr: {status_output.stderr}")
            except FileNotFoundError:
                logging.warning("systemctl غير موجود. لا يمكن التحقق من حالة خدمة Tor عبر systemctl.")
            except Exception as e:
                logging.warning(f"خطأ عند التحقق من حالة خدمة Tor عبر systemctl: {e}")

            # التحقق من المنافذ
            # منفذ SOCKS الرئيسي
            port_9050_available = False
            sock_9050 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_9050.settimeout(5) # تعيين مهلة للاتصال
            result_9050 = sock_9050.connect_ex(('127.0.0.1', 9050))
            sock_9050.close()
            if result_9050 == 0:
                logging.info("المنفذ 9050 (SOCKS) متاح.")
                port_9050_available = True
            else:
                logging.warning("المنفذ 9050 (SOCKS) غير متاح.")
                # لا نرجع False فورًا، قد يكون منفذ التحكم كافيًا لبعض العمليات أو قد يكون المستخدم يستخدم منفذًا مختلفًا
            
            # منفذ التحكم (اختياري للاستخدام العام، لكن جيد للتحقق)
            port_9051_available = False
            sock_9051 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_9051.settimeout(5)
            result_9051 = sock_9051.connect_ex(('127.0.0.1', 9051))
            sock_9051.close()
            if result_9051 == 0:
                logging.info("المنفذ 9051 (ControlPort) متاح.")
                port_9051_available = True
            else:
                logging.warning("المنفذ 9051 (ControlPort) غير متاح. تجديد دوائر Tor قد لا يعمل.")

            if not port_9050_available:
                logging.error("منفذ Tor SOCKS (9050) الرئيسي غير متاح. لا يمكن استخدام Tor.")
                return False

            # اختبار الاتصال الفعلي عبر بروكسي Tor (إذا كان المنفذ 9050 متاحًا)
            # هذا هو الاختبار الأهم
            logging.info("محاولة اختبار الاتصال الفعلي عبر بروكسي Tor (127.0.0.1:9050)...")
            session = requests.Session()
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            
            # استخدام هيدر بسيط للاختبار
            test_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'}

            response = session.get('https://check.torproject.org/', timeout=20, headers=test_headers) # زيادة المهلة
            if 'Congratulations. This browser is configured to use Tor.' in response.text or 'مبارك. هذا المتصفح مهيأ لاستخدام Tor.' in response.text:
                logging.info("✅ تم التحقق من خدمة Tor بنجاح والاتصال عبرها يعمل.")
                return True
            else:
                logging.error(f"❌ الاتصال ليس عبر شبكة Tor أو فشل التحقق. محتوى الصفحة: {response.text[:200]}...") # طباعة جزء من المحتوى للمساعدة في التشخيص
                return False

        except requests.exceptions.ProxyError as e:
            logging.error(f"خطأ بروكسي عند التحقق من خدمة Tor (ربما Tor لا يعمل أو المنفذ 9050 مغلق): {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            logging.error(f"خطأ اتصال عند التحقق من خدمة Tor (ربما check.torproject.org معطل أو هناك مشكلة شبكة): {e}")
            return False
        except requests.exceptions.Timeout:
            logging.error("انتهت مهلة الاتصال عند محاولة التحقق من خدمة Tor عبر check.torproject.org.")
            return False
        except Exception as e:
            logging.error(f"خطأ غير متوقع في التحقق من خدمة Tor: {str(e)}")
            return False

    def check_tor_status(self):
        """التحقق من حالة Tor (هذه الدالة مشابهة لـ verify_tor_service ولكن أقل تفصيلاً)"""
        # يمكن تبسيط هذه الدالة أو دمجها مع verify_tor_service
        # حاليًا، verify_tor_service هي الأكثر شمولاً
        logging.info("التحقق من حالة Tor (check_tor_status)...")
        try:
            # التحقق من المنافذ
            for port in [9050]: # التركيز على منفذ SOCKS الأساسي
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
            
            # إعداد قائمة تكوينات البروكسي للمترجمين
            translator_proxy_options = []
            if self.tor_enabled: # التحقق من تفعيل Tor
                # أضف بروكسيات Tor فقط إذا كان Tor مفعلًا وتم إعداد بروكسيات Tor عاملة
                tor_proxies_available = [p for p in self.proxies if p['type'] == 'tor' and p['url']]
                for tor_proxy in tor_proxies_available:
                    translator_proxy_options.append({
                        'http': tor_proxy['url'],
                        'https': tor_proxy['url']
                    })
            
            # إضافة خيار عدم استخدام بروكسي (اتصال مباشر) دائمًا
            translator_proxy_options.append(None)

            for proxy_setting in translator_proxy_options:
                try:
                    translator = GoogleTranslator(
                        source='en',
                        target='ar',
                        proxies=proxy_setting, # استخدام None للاتصال المباشر
                        timeout=30
                    )
                    
                    if hasattr(translator, 'session'):
                        translator.session.verify = True
                        translator.session.trust_env = False
                        # استخدام self.headers التي تم إعدادها مسبقًا
                        translator.session.headers.update(self.headers if hasattr(self, 'headers') else self.get_fallback_headers())
                        
                        adapter = requests.adapters.HTTPAdapter(
                            pool_connections=5,
                            pool_maxsize=10,
                            max_retries=3,
                            pool_block=False
                        )
                        translator.session.mount('http://', adapter)
                        translator.session.mount('https://', adapter)
                    
                    # اختبار المترجم
                    # قد يكون من الأفضل عدم اختبار الترجمة هنا لتجنب استهلاك مبكر للحصص أو حظر IP
                    # سنفترض أن المترجم يعمل إذا تم إنشاؤه بنجاح
                    self.translators.append(translator)
                    proxy_name = "Direct" if proxy_setting is None else proxy_setting.get('http', 'Unknown Tor Proxy')
                    logging.info(f"تم إضافة مترجم جديد (عبر: {proxy_name})")
                    
                except Exception as e:
                    proxy_name_on_fail = "Direct" if proxy_setting is None else proxy_setting.get('http', 'Unknown Tor Proxy')
                    logging.warning(f"فشل في إعداد المترجم مع الإعداد {proxy_name_on_fail}: {str(e)}")
                    continue

            if not self.translators:
                logging.error("لم يتم إعداد أي مترجمين بنجاح. محاولة أخيرة بمترجم مباشر.")
                # إضافة مترجم مباشر كحل أخير إذا فشلت جميع المحاولات الأخرى
                self.translators.append(GoogleTranslator(source='en', target='ar'))
                logging.warning("تم إعداد مترجم مباشر فقط كحل أخير.")
            
            self.current_translator_index = 0
            logging.info(f"تم إعداد {len(self.translators)} مترجم بنجاح.")

        except Exception as e:
            logging.error(f"خطأ فادح في إعداد المترجمين: {str(e)}")
            # إعداد مترجم واحد للطوارئ إذا فشل كل شيء آخر
            self.translators = [GoogleTranslator(source='en', target='ar')]
            self.current_translator_index = 0
            logging.warning("تم الرجوع إلى مترجم مباشر واحد فقط بسبب خطأ في إعداد المترجمين.")

    def get_fallback_headers(self):
        """إنشاء هيدرز احتياطية بسيطة"""
        logging.info("استخدام هيدرز احتياطية.")
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def renew_tor_circuit(self):
        """محاولة تجديد دائرة Tor."""
        if not self.tor_enabled:
            logging.warning("Tor غير مفعل، لا يمكن تجديد الدائرة.")
            return False

        logging.info("محاولة تجديد دائرة Tor عبر request_new_tor_circuit...")
        return self.request_new_tor_circuit()

    def rotate_translator(self):
        """تدوير المترجم المستخدم."""
        if self.translators and len(self.translators) > 1:
            self.current_translator_index = (self.current_translator_index + 1) % len(self.translators)
            logging.info(f"تم التبديل إلى المترجم رقم: {self.current_translator_index}")
        else:
            logging.info("لا يوجد مترجمون إضافيون للتبديل إليهم أو يوجد مترجم واحد فقط.")

    def cleanup(self):
        """تنظيف الموارد عند انتهاء البرنامج."""
        logging.info("بدء عملية التنظيف...")
        # حاليًا لا توجد موارد محددة تحتاج إلى تنظيف صريح هنا
        # يمكن إضافة إغلاق اتصالات أو حذف ملفات مؤقتة إذا لزم الأمر في المستقبل
        logging.info("اكتملت عملية التنظيف.")


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
            
            if self.tor_enabled: # التحقق من تفعيل Tor
                # البروكسي الأساسي لـ Tor
                primary_tor_config = {
                    'url': 'socks5h://127.0.0.1:9050',
                    'name': 'Tor Primary (9050)',
                    'type': 'tor'
                }
                if self.test_proxy(primary_tor_config['url']):
                    self.proxies.append(primary_tor_config)
                    logging.info(f"تم إضافة بروكسي Tor الأساسي: {primary_tor_config['name']}")
                else:
                    logging.warning(f"فشل اختبار بروكسي Tor الأساسي {primary_tor_config['name']} ({primary_tor_config['url']}). لن يتم إضافته. تأكد أن خدمة Tor تعمل على هذا المنفذ.")

                # بروكسي Tor Browser (اختياري ويعتبر ثانوي)
                tor_browser_proxy_config = {
                    'url': 'socks5h://127.0.0.1:9150',
                    'name': 'Tor Browser (9150)',
                    'type': 'tor'
                }
                # اختباره بهدوء أكبر، لأنه أقل أهمية من الأساسي
                if self.test_proxy(tor_browser_proxy_config['url'], timeout=5): # مهلة أقصر للاختبار
                    self.proxies.append(tor_browser_proxy_config)
                    logging.info(f"تم إضافة بروكسي Tor Browser: {tor_browser_proxy_config['name']}")
                else:
                    logging.info(f"بروكسي Tor Browser {tor_browser_proxy_config['name']} ({tor_browser_proxy_config['url']}) غير متاح أو فشل اختباره. هذا طبيعي إذا لم يكن متصفح Tor يعمل.")
            else:
                logging.info("Tor غير مفعل (self.tor_enabled = False). لن يتم إعداد بروكسيات Tor.")

            # إضافة اتصال مباشر كخيار دائم وأساسي
            self.proxies.append({
                'url': None,
                'name': 'Direct Connection',
                'type': 'direct'
            })
            
            # ضمان أن قائمة البروكسيات ليست فارغة (على الأقل الاتصال المباشر)
            if not self.proxies:
                 self.proxies.append({'url': None, 'name': 'Direct Connection', 'type': 'direct'})

            self.current_proxy_index = 0
            self.consecutive_failures = 0 # إعادة تعيين عداد الفشل عند إعداد البروكسيات
            
            logging.info(f"تم إعداد {len(self.proxies)} بروكسي.")
            if any(p['type'] == 'tor' for p in self.proxies):
                logging.info("تم تضمين بروكسيات Tor.")
            else:
                logging.warning("لم يتم إعداد أي بروكسيات Tor عاملة. سيتم الاعتماد على الاتصال المباشر بشكل أساسي.")
            
        except Exception as e:
            logging.error(f"خطأ فادح في إعداد البروكسيات: {str(e)}")
            # إعداد اتصال مباشر كحل طوارئ إذا فشل كل شيء آخر
            self.proxies = [{'url': None, 'name': 'Direct Connection', 'type': 'direct'}]
            self.current_proxy_index = 0
            logging.warning("تم الرجوع إلى الاتصال المباشر فقط بسبب خطأ في إعداد البروكسيات.")

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
                # تجديد اتصال Tor قبل كل محاولة إذا كان Tor مفعل والبروكسي الحالي هو Tor
                current_proxy_settings = self.proxies[self.current_proxy_index]
                if attempt > 0 and self.tor_enabled and current_proxy_settings['type'] == 'tor':
                    logging.info(f"محاولة تجديد دائرة Tor قبل المحاولة {attempt + 1} للترجمة...")
                    if self.renew_tor_circuit():
                        time.sleep(2)  # انتظار بعد تجديد المسار الناجح
                    else:
                        logging.warning("فشل تجديد دائرة Tor، الاستمرار بالدائرة الحالية أو البروكسي الحالي.")

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
            for item in preserved:
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
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
        if processor:
            processor.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
        sys.exit(0)