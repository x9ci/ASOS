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
import stem
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
CURRENT_USER = os.getenv('USER', 'unknown') # User for logging purposes

# الإعدادات العامة
CURRENT_USER = "x9up"  # تعديل اسم المستخدم حسب المدخل (User override for specific context)
MAX_RETRIES = 3  # Maximum number of retries for a failing translation attempt on a single chunk
DELAY_MIN = 2  # Minimum delay in seconds between translation requests
DELAY_MAX = 5  # Maximum delay in seconds between translation requests
CHUNK_SIZE = 1000  # Approximate size in characters for splitting text blocks for translation
MAX_CONSECUTIVE_FAILURES = 3  # Number of consecutive failures on a translator before trying to rotate translator/proxy

# ملاحظة: تمت إزالة الدالة setup_tor() وإعداد SOCKS العام.
# يجب أن يعتمد البرنامج النصي الآن على تثبيت وتهيئة TOR حالية.

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

            # التحقق من خدمة Tor القائمة
            # This script expects TOR to be pre-configured and running.
            if not self.verify_tor_service():
                # تم تحديث الرسالة في verify_tor_service لتكون أكثر إفادة
                raise Exception("فشل التحقق من خدمة TOR. يرجى التأكد من أن خدمة TOR تعمل وأن المنافذ الضرورية متاحة.")

            # إعداد الاتصال عبر Tor (مثل طلب دائرة جديدة)
            # This step attempts to connect to the TOR ControlPort to request a new circuit (IP address).
            # تم تعديل setup_tor_connection لعدم إعادة تشغيل الخدمة
            if not self.setup_tor_connection(): # استبدال setup_advanced_connection
                raise Exception("فشل في إعداد الاتصال عبر TOR (مثل طلب دائرة جديدة).")

            # إعداد البروكسيات
            self.setup_proxies()
            
            # إعداد User-Agent والهيدرز
            try:
                # Changed UserAgent initialization to remove verify_ssl=False
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
            logging.error(f"❌ فشل في تهيئة المعالج: {str(e)}", exc_info=True)
            # توفير رسالة واضحة للمستخدم باللغة العربية قبل إعادة رفع الاستثناء
            raise Exception(f"❌ فشل تهيئة معالج النصوص. تفاصيل الخطأ مسجلة. الخطأ الأصلي: {str(e)}")

    def setup_tor_connection(self):
        """إعداد الاتصال بوحدة تحكم Tor وطلب دائرة جديدة."""
        # This function connects to the TOR ControlPort (default 9051) to signal for a new TOR circuit.
        # A new circuit means a new exit IP address, which can help avoid IP-based blocking.
        try:
            # لا تقم بإعادة تشغيل خدمة Tor هنا
            logging.info("محاولة الاتصال بوحدة تحكم Tor لطلب دائرة جديدة...")

            # Connect to TOR's ControlPort (default: 127.0.0.1:9051)
            with Controller.from_port(address="127.0.0.1", port=9051) as controller:
                try:
                    # محاولة المصادقة باستخدام ملف تعريف الارتباط (cookie) أولاً
                    # TOR often uses cookie authentication by default.
                    controller.authenticate()
                    logging.info("✅ تمت المصادقة مع وحدة تحكم Tor بنجاح (ملف تعريف الارتباط).")
                except Exception as auth_cookie_error:
                    logging.warning(f"فشلت المصادقة باستخدام ملف تعريف الارتباط: {auth_cookie_error}. قد تحتاج إلى كلمة مرور إذا تم تكوينها.")
                    # لا تفشل هنا، فقط سجل التحذير. NEWNYM قد يعمل بدون مصادقة في بعض التكوينات.
                
                # Request a new TOR circuit. Signal.NEWNYM tells TOR to establish a new clean circuit.
                controller.signal(Signal.NEWNYM)
                # انتظر حتى تكون الدائرة الجديدة جاهزة (اختياري ولكن موصى به)
                # get_newnym_wait() provides an estimated time TOR needs to build the new circuit.
                time.sleep(controller.get_newnym_wait()) 
                logging.info("✅ تم طلب دائرة Tor جديدة بنجاح.")
            return True

        except stem.SocketError as se:
            logging.error(f"❌ خطأ في الاتصال بمقبس Tor (ControlPort): {str(se)}", exc_info=True)
            logging.error("يرجى التأكد من أن خدمة TOR تعمل وأن منفذ التحكم (عادة 9051) متاح ويمكن الوصول إليه.")
            return False
        except stem.connection.AuthenticationFailure as af:
            logging.error(f"❌ فشل المصادقة مع وحدة تحكم Tor: {str(af)}", exc_info=True)
            logging.error("يرجى التحقق من تكوين مصادقة منفذ التحكم لـ Tor (مثل كلمة المرور أو ملف تعريف الارتباط).")
            return False
        except stem.ProtocolError as pe:
            logging.error(f"❌ خطأ في بروتوكول وحدة تحكم Tor: {str(pe)}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"❌ خطأ غير متوقع في إعداد اتصال Tor أو طلب دائرة جديدة: {str(e)}", exc_info=True)
            logging.error("يرجى التأكد من أن خدمة TOR تعمل وأن منفذ التحكم (عادة 9051) متاح ومكون بشكل صحيح.")
            return False

    def verify_tor_service(self):
        """التحقق من أن منافذ SOCKS والتحكم لـ Tor تستمع، واختبار الاتصال."""
        # This function checks if TOR is likely running and accessible.
        # It expects TOR to be pre-configured and listening on standard ports.
        logging.info("التحقق من حالة خدمة Tor الحالية...")
        ports_ok = True
        # Default TOR SOCKS port is 9050, ControlPort is 9051.
        for port_name, port_num in [("SOCKS", 9050), ("ControlPort", 9051)]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5) # مهلة قصيرة للتحقق من المنفذ
            result = sock.connect_ex(('127.0.0.1', port_num)) # Check if port is open
            sock.close()
            if result == 0:
                logging.info(f"✅ منفذ Tor {port_name} ({port_num}) يستمع.")
            else:
                logging.error(f"❌ منفذ Tor {port_name} ({port_num}) لا يستمع أو غير متاح.")
                ports_ok = False
        
        if not ports_ok:
            logging.error("فشل الاتصال بـ TOR. يرجى التأكد من أن خدمة TOR تعمل وأن منفذ SOCKS (9050) ومنفذ التحكم (9051) متاحان ومكونان بشكل صحيح.")
            return False

        # اختبار الاتصال عبر Tor SOCKS proxy
        logging.info("اختبار الاتصال عبر بروكسي Tor SOCKS...")
        try:
            session = requests.Session()
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            # استخدم رأس User-Agent لتجنب الحظر المحتمل
            headers = {'User-Agent': 'Mozilla/5.0'} # يمكن استخدام self.get_advanced_headers() إذا كانت متاحة ومناسبة هنا
            response = session.get('https://check.torproject.org/', timeout=20, headers=headers) # زيادة المهلة قليلاً
            
            # النص المتوقع قد يختلف قليلاً بناءً على اللغة أو تحديثات الموقع
            # نتحقق من وجود جزء أساسي من رسالة النجاح
            if 'Congratulations' in response.text and 'Tor' in response.text:
                logging.info("✅ تم التحقق من الاتصال عبر بروكسي Tor SOCKS بنجاح.")
                return True
            else:
                logging.error("❌ فشل التحقق من الاتصال عبر بروكسي Tor SOCKS. الرد لا يحتوي على رسالة النجاح المتوقعة.")
                logging.debug(f"محتوى الرد من check.torproject.org: {response.text[:500]}") # سجل جزءًا من الرد للمساعدة في التشخيص
                return False
                
        except requests.exceptions.Timeout:
            logging.error("Timeout occurred while trying to connect to check.torproject.org through Tor SOCKS proxy.", exc_info=True)
            logging.error("فشل الاتصال بـ TOR بسبب انتهاء المهلة. قد تكون الشبكة بطيئة أو TOR غير قادر على إنشاء دائرة.")
            return False
        except requests.exceptions.ConnectionError:
            logging.error("Connection error while trying to connect to check.torproject.org through Tor SOCKS proxy.", exc_info=True)
            logging.error("فشل الاتصال بـ TOR. تأكد أن خدمة TOR تعمل وأن المنفذ 9050 SOCKS متاح.")
            return False
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ خطأ أثناء اختبار الاتصال عبر بروكسي Tor SOCKS: {str(e)}", exc_info=True)
            logging.error("فشل الاتصال بـ TOR. يرجى التأكد من أن خدمة TOR تعمل وأن منفذ SOCKS (9050) متاح ومكون بشكل صحيح.")
            return False
        except Exception as e:
            logging.error(f"❌ خطأ غير متوقع أثناء اختبار الاتصال عبر بروكسي Tor SOCKS: {str(e)}", exc_info=True)
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
            
        except FileNotFoundError:
            logging.error("لم يتم العثور على الأمر 'systemctl'. هل هذا نظام غير قائم على systemd؟", exc_info=True)
            return False # لا يمكن التحقق من الحالة
        except subprocess.CalledProcessError as cpe:
            logging.error(f"خطأ أثناء تنفيذ أمر التحقق من حالة Tor: {cpe}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"خطأ غير متوقع في التحقق من حالة Tor: {str(e)}", exc_info=True)
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
    
    def get_fallback_headers(self):
        logging.info("Using fallback headers as UserAgent initialization failed or was skipped.")
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate', # Added standard encoding
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache', # Added standard cache control
            'Pragma': 'no-cache' # Added standard pragma
        }
    
    def verify_system_requirements(self):
        """التحقق من متطلبات النظام والمكتبات"""
        try:
            # التحقق من إصدار Python
            python_version = sys.version_info
            if python_version < (3, 7):
                raise Exception(f"يتطلب Python 3.7 أو أحدث. الإصدار الحالي: {python_version.major}.{python_version.minor}")

            # التحقق من المكتبات المطلوبة
            required_packages = {
                'deep_translator': '1.8.0', # تأكد من توافق الإصدارات
                'requests': '2.25.0', # تأكد من توافق الإصدارات
                'fake_useragent': '0.1.11', # تأكد من توافق الإصدارات
                'stem': '1.8.0', # تأكد من توافق الإصدارات
                'pysocks': '1.7.1',  # اسم الحزمة لـ pip install
                'arabic_reshaper': '2.1.3', # تأكد من توافق الإصدارات
                'python-bidi': '0.4.2',   # اسم الحزمة لـ pip install
                'psutil': '5.8.0' # تأكد من توافق الإصدارات
            }

            missing_packages = []
            for package_pip_name in required_packages:
                try:
                    # اسم الحزمة عند الاستيراد قد يختلف
                    import_name = package_pip_name
                    if package_pip_name == 'pysocks':
                        import_name = 'socks'  # PySocks يتم استيرادها كـ socks
                    elif package_pip_name == 'python-bidi':
                        import_name = 'bidi'   # python-bidi يتم استيرادها كـ bidi
                    
                    __import__(import_name)
                    logging.info(f"✅ تم العثور على مكتبة {package_pip_name} (مستوردة كـ {import_name})")
                except ImportError as e:
                    logging.error(f"❌ لم يتم العثور على مكتبة {package_pip_name} (محاولة استيراد {import_name}): {str(e)}")
                    missing_packages.append(package_pip_name)

            if missing_packages:
                logging.error(f"المكتبات المفقودة: {', '.join(missing_packages)}. يرجى تثبيتها باستخدام pip install.")
                return False

            # لم نعد نتحقق من تثبيت Tor هنا، بل نعتمد على توفره كخدمة.
            # logging.info("تم تخطي التحقق من تثبيت Tor بشكل مباشر، سيتم التحقق من الخدمة لاحقاً.")

            # التحقق من الذاكرة المتاحة
            memory = psutil.virtual_memory()
            if memory.available < 500 * 1024 * 1024:  # 500 MB
                logging.error("❌ الذاكرة المتاحة غير كافية")
                return False

            logging.info("✅ تم التحقق من متطلبات النظام بنجاح")
            return True

        except ImportError as ie:
            # هذا الاستثناء يجب أن يتم التعامل معه داخل الحلقة، لكن كإجراء احترازي
            logging.error(f"فشل استيراد مكتبة ضرورية: {str(ie)}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"❌ فشل التحقق من متطلبات النظام: {str(e)}", exc_info=True)
            return False
    
    # def check_tor_installation(self): # تم حذف هذه الدالة، الاعتماد على الخدمة الحالية
    #     """التحقق من تثبيت Tor"""
    #     try:
    #         # محاولة العثور على مسار Tor
    #         tor_path = subprocess.run(
    #             ['which', 'tor'],
    #             capture_output=True,
    #             text=True
    #         ).stdout.strip()

    #         if not tor_path:
    #             return False

    #         # التحقق من الإصدار
    #         tor_version = subprocess.run(
    #             ['tor', '--version'],
    #             capture_output=True,
    #             text=True
    #         ).stdout

    #         if tor_version:
    #             logging.info(f"إصدار Tor: {tor_version.split()[2]}")
    #             return tor_path

    #         return False

    #     except Exception as e:
    #         logging.error(f"خطأ في التحقق من تثبيت Tor: {str(e)}")
    #         return False

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
            logging.error(f"خطأ في التحقق من موارد النظام: {str(e)}", exc_info=True)
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

        except OSError as ose:
            logging.warning(f"خطأ في نظام التشغيل أثناء التحقق من الصلاحيات (مثل إنشاء مجلد أو ملف): {ose}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"خطأ غير متوقع في التحقق من الصلاحيات: {str(e)}", exc_info=True)
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

        except psutil.Error as pse:
            logging.error(f"خطأ متعلق بـ psutil أثناء جمع معلومات النظام: {pse}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"خطأ غير متوقع في جمع معلومات النظام: {str(e)}", exc_info=True)
            return None
    
    def setup_translators(self):
        """إعداد المترجمين مع تحسينات الأمان ودعم MyMemoryTranslator."""
        try:
            # تعطيل IPv6
            requests.packages.urllib3.util.connection.HAS_IPV6 = False
            
            self.translators = [] # List to hold initialized translator instances
            translator_types = [GoogleTranslator, MyMemoryTranslator] # Translator classes to try
            
            # إعداد قائمة البروكسيات المتنوعة (كما كانت معرفة سابقاً)
            # These are the proxy configurations that will be attempted with each translator type.
            # 'None' represents a direct connection (no proxy).
            proxy_configs = [
                { # TOR SOCKS proxy on default port 9050
                    'http': 'socks5h://127.0.0.1:9050',
                    'https': 'socks5h://127.0.0.1:9050'
                },
                { # TOR SOCKS proxy often used by TOR Browser on port 9150
                    'http': 'socks5h://127.0.0.1:9150',
                    'https': 'socks5h://127.0.0.1:9150'
                },
                None  # مترجم مباشر للطوارئ (Direct connection attempt)
            ]

            # Iterate through each proxy configuration and then through each translator type.
            for proxy_config in proxy_configs: 
                for translator_class in translator_types:
                    try:
                        translator_instance_name = translator_class.__name__
                        logging.info(f"محاولة إعداد {translator_instance_name} مع بروكسي: {proxy_config if proxy_config else 'مباشر'}")

                        # Initialize MyMemoryTranslator
                        if translator_class == MyMemoryTranslator:
                            translator = translator_class(
                                source='en', 
                                target='ar',
                                proxies=proxy_config, # Pass proxy config. Behavior depends on deep_translator's implementation for MyMemory.
                                timeout=30
                            )
                            # ملاحظة: MyMemoryTranslator قد يتطلب تكوينًا مختلفًا للبروكسي إذا لم يتم تمريره عبر deep_translator
                            # إذا كان MyMemoryTranslator لا يدعم proxies مباشرة في deep_translator, 
                            # قد تحتاج session.proxies إلى التعيين يدويًا إذا كان ذلك ممكنًا.
                        # Initialize GoogleTranslator
                        else: # GoogleTranslator
                            translator = translator_class(
                                source='en', 
                                target='ar', 
                                proxies=proxy_config, # Pass proxy config. GoogleTranslator in deep_translator uses requests.Session.
                                timeout=30
                            )
                        
                        # Configure session for translators that use requests.Session (like GoogleTranslator)
                        if hasattr(translator, 'session'): # GoogleTranslator لديه session
                            translator.session.verify = True # Verify SSL certificates
                            translator.session.trust_env = False # Important for ensuring proxy usage if set
                            translator.session.headers.update(self.get_advanced_headers())
                            adapter = requests.adapters.HTTPAdapter(
                                pool_connections=5,
                                pool_maxsize=10,
                                max_retries=3, # محاولات إعادة الاتصال على مستوى الجلسة
                                pool_block=False
                            )
                            translator.session.mount('http://', adapter)
                            translator.session.mount('https://', adapter)
                        elif translator_class == MyMemoryTranslator:
                            # MyMemoryTranslator قد لا يستخدم session بنفس الطريقة.
                            # إذا كنت بحاجة إلى تمرير بروكسي ولم يتم ذلك عبر deep_translator,
                            # قد تحتاج إلى طريقة أخرى (مثلاً, إذا كانت المكتبة تسمح بتمرير session مخصصة).
                            # حاليًا, نعتمد على ما يوفره deep_translator.
                            pass
                        
                        # اختبار المترجم
                        test_text = "test"
                        test_translation = translator.translate(test_text)
                        
                        # MyMemoryTranslator يمكن أن يعيد قائمة أو None
                        if translator_class == MyMemoryTranslator and isinstance(test_translation, list):
                            test_translation = test_translation[0] if test_translation else None
                        
                        if test_translation and isinstance(test_translation, str):
                            self.translators.append(translator)
                            logging.info(f"✅ تم إضافة {translator_instance_name} (بروكسي: {proxy_config if proxy_config else 'مباشر'}) بنجاح بعد الاختبار.")
                        else:
                            logging.warning(f"⚠️ فشل في الحصول على ترجمة اختبار صالحة من {translator_instance_name} (بروكسي: {proxy_config if proxy_config else 'مباشر'}). الرد: {test_translation}")

                    except requests.exceptions.RequestException as re:
                        logging.warning(f"❌ خطأ اتصال أثناء إعداد/اختبار {translator_class.__name__} مع البروكسي {proxy_config if proxy_config else 'مباشر'}: {str(re)}", exc_info=True)
                    except Exception as e:
                        logging.warning(f"❌ فشل في إعداد {translator_class.__name__} مع البروكسي {proxy_config if proxy_config else 'مباشر'}: {str(e)}", exc_info=True)
                        continue
            
            if not self.translators:
                # محاولة أخيرة: GoogleTranslator مباشر
                try:
                    logging.info("لم يتم إعداد أي مترجم. محاولة أخيرة مع GoogleTranslator مباشر...")
                    gt = GoogleTranslator(source='en', target='ar')
                    # اختبار بسيط للمترجم الاحتياطي
                    if gt.translate("test"):
                        self.translators.append(gt)
                        logging.warning("⚠️ تم تكوين GoogleTranslator مباشر فقط كحل أخير.")
                    else:
                         logging.error("🛑 حرج: فشل المترجم الاحتياطي GoogleTranslator المباشر أيضًا في التهيئة بعد الاختبار.", exc_info=True) # Add exc_info
                except Exception as e:
                    logging.error(f"🛑 حرج: فشل في تهيئة المترجم الاحتياطي GoogleTranslator المباشر: {str(e)}", exc_info=True)

            self.current_translator_index = 0
            if self.translators:
                logging.info(f"✅ تم إعداد {len(self.translators)} مترجم بنجاح.")
            else:
                logging.error("🛑 لم يتمكن من إعداد أي مترجم. لن تعمل الترجمة. تحقق من إعدادات الشبكة والبروكسي.")

        except Exception as e: # خطأ عام في setup_translators
            logging.error(f"❌ خطأ كبير في دالة setup_translators: {str(e)}", exc_info=True)
            # تأكد من وجود self.translators كقائمة فارغة على الأقل
            if not hasattr(self, 'translators'):
                 self.translators = []
            if not self.translators: # إذا فشل كل شيء، حاول إضافة مترجم مباشر واحد كملجأ أخير
                try:
                    gt_direct = GoogleTranslator(source='en', target='ar')
                    if gt_direct.translate("final fallback test"):
                        self.translators.append(gt_direct)
                        logging.warning("تم اللجوء إلى إضافة GoogleTranslator مباشر بسبب خطأ كبير في setup_translators.")
                    else:
                        logging.error("فشل اختبار الملاذ الأخير GoogleTranslator.", exc_info=True)
                except Exception as final_fallback_e:
                    logging.error(f"فشل حتى الملاذ الأخير لإضافة GoogleTranslator: {final_fallback_e}", exc_info=True)
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

        except OSError as ose:
            print(f"خطأ في نظام التشغيل أثناء إعداد التسجيل (مثل إنشاء مجلد السجلات): {ose}")
            # لا يمكن استخدام logging هنا إذا فشل إعداده
            return False
        except Exception as e:
            print(f"خطأ غير متوقع في إعداد التسجيل: {str(e)}")
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
            logging.error(f"خطأ في إعداد البروكسيات: {str(e)}", exc_info=True)
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

        except requests.exceptions.Timeout:
            logging.warning(f"انتهت مهلة اختبار البروكسي {proxy_url}", exc_info=True)
        except requests.exceptions.ConnectionError:
            logging.warning(f"خطأ اتصال عند اختبار البروكسي {proxy_url}", exc_info=True)
        except requests.exceptions.RequestException as e:
            logging.warning(f"فشل اختبار البروكسي {proxy_url} بسبب خطأ طلب: {str(e)}", exc_info=True)
        except Exception as e:
            logging.warning(f"فشل اختبار البروكسي {proxy_url} بسبب خطأ غير متوقع: {str(e)}", exc_info=True)

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
                    logging.warning("فشل تجديد دائرة Tor، قد يستمر استخدام الدائرة القديمة أو بروكسي آخر.")
                
            # تأخير عشوائي قبل استخدام البروكسي الجديد
            time.sleep(random.uniform(1, 3))
            
            logging.info(f"تم التبديل من {previous_proxy['name']} إلى {current_proxy['name']}")
            return True
            
        except Exception as e:
            logging.error(f"خطأ في تدوير البروكسي: {str(e)}", exc_info=True)
            # العودة للبروكسي السابق في حالة الفشل، إذا كان ذلك ممكناً وآمناً
            try:
                self.current_proxy_index = self.proxies.index(previous_proxy)
            except ValueError: # previous_proxy قد لا يكون موجوداً إذا تم تعديل القائمة
                logging.error("لم يتمكن من العودة إلى البروكسي السابق بعد فشل التدوير.")
                # قد يكون من الأفضل اختيار بروكسي عشوائي أو العودة إلى البروكسي الأول
                if self.proxies:
                    self.current_proxy_index = 0
                else: # لا يوجد بروكسيات متاحة
                    logging.critical("لا توجد بروكسيات متاحة بعد فشل التدوير الكارثي!")
                    # هنا يجب أن يكون هناك تعامل حرج، ربما إنهاء البرنامج أو محاولة وضع الطوارئ
            return False
    
    def translate_with_retry(self, text, max_retries=5):
        """ترجمة النص مع معالجة متقدمة للأخطاء وتغيير المترجمين"""
        if not text or not text.strip():
            return text

        original_text = text
        last_error = None

        for attempt in range(max_retries):
            try:
                # تجديد اتصال Tor قبل كل محاولة إذا لم تكن المحاولة الأولى
                if attempt > 0:
                    logging.info(f"محاولة الترجمة رقم {attempt + 1}. تجديد دائرة Tor...")
                    if not self.renew_tor_circuit(): # استدعاء الدالة المحدثة
                        logging.warning("فشل تجديد دائرة Tor، الاستمرار بالمحاولة على أي حال.")
                    time.sleep(random.uniform(1, 3)) # انتظار قصير بعد تجديد المسار

                # اختيار المترجم
                if not self.translators: # تحقق حاسم (Critical check: if no translators are available)
                    logging.critical("لا يوجد مترجمون مهيئون. لا يمكن المتابعة مع الترجمة.")
                    return original_text # أو إثارة استثناء أعلى (Return original text or raise a higher-level exception)
                
                # Select the current translator and proxy based on their respective indices.
                translator = self.translators[self.current_translator_index]
                translator_name = translator.__class__.__name__
                current_proxy_name = self.proxies[self.current_proxy_index]['name'] if self.proxies else "مباشر"
                
                logging.info(f"محاولة الترجمة باستخدام {translator_name} عبر {current_proxy_name} (محاولة {attempt + 1}/{max_retries})")

                # تحديث الجلسة والهيدرز (Update session and headers for the current attempt)
                if hasattr(translator, 'session'): # If the translator instance has a 'session' attribute (like GoogleTranslator)
                    current_proxy_details = self.proxies[self.current_proxy_index]
                    if current_proxy_details and current_proxy_details['url']: # If a proxy URL is configured
                        translator.session.proxies = { # Set the proxy for the session
                            'http': current_proxy_details['url'],
                            'https': current_proxy_details['url']
                        }
                    else: # إذا كان البروكسي None أو لا يحتوي على URL (الاتصال المباشر) (If proxy is None or no URL, i.e., direct connection)
                        translator.session.proxies = {} # مسح أي بروكسيات سابقة من الجلسة (Clear any previous proxies from the session)
                    translator.session.headers.update(self.get_advanced_headers())
                    translator.session.headers['X-Attempt'] = str(attempt +1) # Add attempt number to headers

                # محاولة الترجمة (Attempt translation)
                result = translator.translate(text.strip())

                # معالجة رد MyMemoryTranslator الذي قد يكون قائمة
                if translator_name == "MyMemoryTranslator" and isinstance(result, list):
                    result = result[0] if result else None
                
                if result and isinstance(result, str):
                    logging.info(f"نجحت الترجمة باستخدام {translator_name} عبر {current_proxy_name}.")
                    self.consecutive_failures = 0  # إعادة تعيين عداد الفشل
                    return result
                else:
                    # سجل إذا لم يكن هناك خطأ ولكن النتيجة غير صالحة
                    logging.warning(f"الترجمة باستخدام {translator_name} عبر {current_proxy_name} أعادت نتيجة غير متوقعة أو فارغة: {result}")
                    # لا نعتبر هذا فشلاً يستدعي تدوير المترجم مباشرة ما لم يثر استثناء

            except Exception as e:
                last_error = str(e)
                translator_name_in_error = self.translators[self.current_translator_index].__class__.__name__ if self.translators else "غير معروف"
                proxy_name_in_error = self.proxies[self.current_proxy_index]['name'] if self.proxies else "مباشر"
                logging.warning(f"فشل المحاولة {attempt + 1} للترجمة باستخدام {translator_name_in_error} عبر {proxy_name_in_error}: {last_error}", exc_info=True)
                
                # زيادة عداد الفشل
                self.consecutive_failures += 1
                
                # تدوير المترجم والبروكسي بعد عدد معين من المحاولات الفاشلة
                # If consecutive failures reach the max limit, rotate translator and proxy.
                if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES: # استخدام ثابت معرف
                    logging.info(f"وصل إلى {self.consecutive_failures} فشل متتالي. محاولة تدوير المترجم والبروكسي.")
                    self.rotate_translator() # Switch to the next available translator
                    self.rotate_proxy()    # Switch to the next available proxy configuration
                    # self.consecutive_failures = 0 # يتم الآن إعادة التعيين داخل rotate_translator (Reset counter is handled in rotate_translator)
                
                # تأخير تصاعدي بين المحاولات (Exponential backoff-like delay)
                time.sleep((attempt + 1) * 2)
                continue

        # إذا فشلت كل المحاولات، نسجل الخطأ ونعيد النص الأصلي
        logging.error(f"فشلت جميع محاولات الترجمة. آخر خطأ: {last_error}")
        return original_text

    def rotate_translator(self):
        """تدوير إلى المترجم التالي المتاح."""
        # This method switches to the next translator in the `self.translators` list.
        # It's called when the current translator fails `MAX_CONSECUTIVE_FAILURES` times.
        if not self.translators or len(self.translators) <= 1:
            logging.warning("⚠️ لا يوجد عدد كاف من المترجمين للتدوير.")
            # إذا كان هناك مترجم واحد أو لا يوجد، حاول تجديد دائرة TOR كإجراء احتياطي.
            # If only one or no translator, try renewing TOR circuit as a fallback action if current proxy is TOR.
            if self.proxies and self.proxies[self.current_proxy_index]['type'] == 'tor':
                 self.renew_tor_circuit() # Attempt to get a new IP via TOR
            return

        previous_translator_name = self.translators[self.current_translator_index].__class__.__name__
        # Cycle to the next translator index
        self.current_translator_index = (self.current_translator_index + 1) % len(self.translators)
        current_translator_name = self.translators[self.current_translator_index].__class__.__name__
        
        logging.info(f"🔄 تم تدوير المترجم من {previous_translator_name} إلى {current_translator_name}")
        self.consecutive_failures = 0 # إعادة تعيين عداد الفشل بعد تبديل المترجم (Reset failure counter after switching)
        
        # قد يكون من الجيد أيضًا الحصول على دائرة TOR جديدة عند تبديل المترجمين
        # إذا كان البروكسي الحالي هو TOR، لتقليل فرص الحظر.
        # Also renew TOR circuit if the current proxy is TOR, to potentially get a new IP.
        current_proxy_config = self.proxies[self.current_proxy_index]
        if current_proxy_config and current_proxy_config.get('type') == 'tor':
            logging.info("🔄 تجديد دائرة Tor كجزء من تدوير المترجم.")
            self.renew_tor_circuit()

    def process_text_block(self, text, chunk_size=CHUNK_SIZE):
        """معالجة النص مع الحفاظ على العناصر المهمة"""
        if not text or not text.strip():
            return text

        try:
            # الأنماط التي يجب حفظها (Patterns for text elements to be preserved from translation)
            preserved_patterns = {
                'page_header': r'=== الصفحة \d+ ===',  # Page headers like "=== الصفحة 123 ==="
                'chapter': r'CHAPTER \w+',  # Chapter titles like "CHAPTER Introduction"
                'numbers': r'\d+\.',  # Numbered list items like "1.", "2."
                'special_chars': r'[•\-\[\]\(\)]',  # Special characters like bullets, hyphens, brackets
                'chess_moves': r'\d+\.\s*[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?',  # Chess notations
                'dates': r'\d{4}[-/]\d{2}[-/]\d{2}',  # Dates like YYYY-MM-DD or YYYY/MM/DD
                'urls': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+' # URLs
            }

            # حفظ العناصر المهمة (Save important elements by replacing them with placeholders)
            # This is done to prevent the translator from altering specific structured text.
            preserved = []
            for pattern_name, pattern in preserved_patterns.items():
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    placeholder = f"[PRESERVED_{len(preserved)}]" # Create a unique placeholder
                    preserved.append({
                        'start': match.start(), # Original start index (will be shifted after replacements)
                        'end': match.end(),     # Original end index
                        'content': match.group(), # The actual text content of the match
                        'type': pattern_name,     # Type of pattern (e.g., 'url', 'chess_move')
                        'placeholder': placeholder
                    })
                    # Replace the matched content with the placeholder in the main text.
                    # This replacement shifts subsequent match indices, so direct index restoration isn't used.
                    # Instead, placeholders are globally replaced back after translation.
                    text = text.replace(match.group(), placeholder, 1) # Replace only the first occurrence in this iteration

            # تقسيم النص إلى أجزاء (Split text into chunks for translation)
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
            logging.error(f"خطأ في معالجة النص: {str(e)}", exc_info=True)
            return text # إعادة النص الأصلي في حالة حدوث خطأ غير معالج

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

            # إنشاء المعلومات الوصفية (Create metadata for the output file)
            metadata = self.create_metadata()

            # تقسيم المحتوى إلى صفحات (Split content by page headers, e.g., "=== الصفحة 1 ===")
            # The regex includes the delimiter in the split results, which is helpful.
            pages = re.split(r'(=== الصفحة \d+ ===)', content)
            total_pages = len([p for p in pages if p.strip()]) # Count non-empty pages
            translated_pages = [] # This list seems unused as pages are written directly
            current_page_num = 1

            # إنشاء ملف الترجمة (Create the output filename with a timestamp)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = os.path.join(
                os.path.dirname(input_filename), # Save in the same directory as the input
                f"translated_{timestamp}.txt"
            )

            # كتابة المعلومات الوصفية (Write metadata to the output file)
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                outfile.write(metadata)
                outfile.write("="*50 + "\n\n") # Separator

                # معالجة كل صفحة (Process each page (or segment between page headers))
                for i, page_content in enumerate(pages):
                    if page_content.strip(): # Process only non-empty segments
                        try:
                            logging.info(f"معالجة الصفحة {current_page_num} من {total_pages}")
                            print(f"جاري معالجة الصفحة {current_page_num} من {total_pages}")

                            # ترجمة الصفحة (Translate the current page/segment content)
                            translated_page_content = self.process_text_block(page_content)
                            # translated_pages.append(translated_page_content) # Redundant if writing directly
                            
                            # كتابة الصفحة مباشرة إلى الملف (Write the translated page directly to the output file)
                            outfile.write(translated_page_content + "\n")
                            outfile.flush()  # ضمان حفظ البيانات (Ensure data is written to disk)
                            
                            current_page_num += 1
                            
                            # تدوير البروكسي كل عدة صفحات (Rotate proxy every few pages to vary connection)
                            if current_page_num % 3 == 0:
                                self.rotate_proxy()
                                
                        except Exception as e:
                            # Log error for the specific page and save the original content for that page.
                            logging.error(f"خطأ في معالجة الصفحة {current_page_num}: {str(e)}", exc_info=True)
                            # في حالة الخطأ، نحفظ النص الأصلي (In case of error, save the original text for this page)
                            outfile.write(page_content + "\n")
                            outfile.flush()

                # كتابة معلومات المعالجة النهائية (Write final processing completion info)
                completion_info = self.create_completion_info(current_page_num - 1)
                outfile.write("\n" + completion_info)

            logging.info(f"تم حفظ الترجمة في: {output_filename}")
            print(f"✅ تم حفظ الترجمة في: {output_filename}")
            return output_filename

        except FileNotFoundError as fnf_error:
            logging.error(f"❌ خطأ: الملف غير موجود: {str(fnf_error)}", exc_info=True)
            raise  # إعادة إثارة الخطأ ليتم التعامل معه في main
        except OSError as os_error:
            logging.error(f"❌ خطأ في نظام التشغيل أثناء معالجة الملف {input_filename}: {str(os_error)}", exc_info=True)
            raise
        except Exception as e:
            logging.error(f"❌ خطأ غير متوقع في معالجة الملف {input_filename}: {str(e)}", exc_info=True)
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
        # التحقق من متطلبات النظام و Tor يتم الآن داخل مُنشئ ChessTextProcessor
        # processor.verify_system_requirements() # This call is redundant, already in __init__
        processor = ChessTextProcessor() # قد يثير استثناءات تتم معالجتها أدناه

        # تحديد مسار الملف
        input_file_path = "/home/dc/Public/fml/output/document.txt" # تأكد من أن هذا المسار صحيح
        logging.info(f"مسار ملف الإدخال المحدد: {input_file_path}")
        if not os.path.exists(input_file_path):
            # رسالة واضحة للمستخدم باللغة العربية
            error_message = f"❌ خطأ فادح: ملف الإدخال '{input_file_path}' غير موجود. يرجى التأكد من صحة المسار وتوفر الملف."
            print(error_message)
            logging.critical(error_message) # استخدام CRITICAL للأخطاء التي تمنع البرنامج من العمل
            sys.exit(1)

        # معالجة الملف
        logging.info(f"بدء معالجة الملف: {input_file_path}")
        output_file = processor.process_file(input_file_path)
        # رسالة نجاح واضحة للمستخدم باللغة العربية
        success_message = f"✅ تمت معالجة الملف بنجاح! تم حفظ الترجمة في: {output_file}"
        print(success_message)
        logging.info(success_message)

    except FileNotFoundError as e: # هذا الاستثناء يجب أن يتم التقاطه الآن داخل process_file أو عند التحقق من المسار أعلاه
        user_message = f"❌ خطأ في العثور على ملف: {str(e)}. يرجى التحقق من اسم الملف والمسار."
        print(user_message)
        logging.error(user_message, exc_info=True)
        sys.exit(1)
    except Exception as e:
        # رسالة خطأ عامة وواضحة للمستخدم باللغة العربية
        user_message = f"❌ حدث خطأ فادح غير متوقع أثناء تشغيل البرنامج. تفاصيل الخطأ مسجلة. الخطأ: {str(e)}"
        print(user_message)
        logging.critical(user_message, exc_info=True) # استخدام CRITICAL للأخطاء الفادحة
        sys.exit(1)
    finally:
        # تنظيف الموارد
        if processor:
            # processor.cleanup() # لا توجد دالة cleanup معرفة حاليًا
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
        sys.exit(0)
