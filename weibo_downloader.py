#修复按照时间截止的逻辑，遇到截止时间退出爬取
import os
import re
import time
import json
import requests
from datetime import datetime
import logging
from urllib.parse import urlparse

COOKIE = ""

# 基础配置
SESSION = requests.Session()

class Config:
    def __init__(self, uid_list=None):
        """初始化 Config 类，设置基本配置"""
        self.COOKIE = self.get_cookie()
        self.uid_list = uid_list if uid_list else self.get_uid_list()
        self.uid = None  # 当前处理的 UID
        self.download_dir = None
        self.username = None
        self.interval = self.get_interval()
        self.username_cache = {}  # 用于缓存用户名
        self.saved_url_filename = None
        self.unsaved_url_filename = None
        self.date_log_filename = None
        # 提示用户输入基目录
        base_dir_input = input("请输入保存文件的基目录（默认 C:\\Base1\\weibo）:").strip()
        self.base_dir = base_dir_input if base_dir_input else "C:\\Base1\\weibo"
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def get_cookie(self):
        """获取并验证微博 Cookie"""
        global COOKIE
        cookie_length = 100
        if len(COOKIE) > cookie_length:
            return COOKIE
        else:
            while len(COOKIE) <= cookie_length:
                print(f"Cookie 长度小于 {cookie_length}，全局变量 COOKIE 的长度太短，可能是错误的，请重新输入")
                COOKIE = input("请输入微博 Cookie（必填）:").strip()
            return COOKIE

    def get_uid_list(self):
        """获取 UID 列表，支持用户输入或使用默认值"""
        default_uid = ["2668367923", "5491928243", "2273396007"]
        result = ",".join(default_uid)
        print(f"回车默认下载 UID 为: {result}")
        uid_input = input("请输入用户 UID,多个 UID 用逗号分隔:").strip()
        if uid_input:
            uid_list = [uid.strip() for uid in uid_input.split(',')]
        else:
            uid_list = default_uid
        return uid_list

    def get_username(self, uid):
        """通过微博 API 获取用户昵称，支持缓存"""
        if uid in self.username_cache:
            return self.username_cache[uid]
        url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Cookie": self.COOKIE
        }
        try:
            time.sleep(3)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                username = data.get('data', {}).get('userInfo', {}).get('screen_name', f"用户_{uid}")
                self.username_cache[uid] = username
                return username
            else:
                print(f"API 请求失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"获取用户名异常: {e}")
        return f"用户_{uid}"

    def get_download_dir(self, base_dir, uid):
        """获取或创建下载目录，基于用户名和 UID"""
        for subdir in os.listdir(base_dir):
            subdir_path = os.path.join(base_dir, subdir)
            if os.path.isdir(subdir_path) and uid in subdir:
                print(f'检测到同名文件夹 "{uid}"，跳过通过API获取用户名')
                return subdir_path
        username = self.get_username(uid)
        new_folder_name = f"{username}_{uid}"
        new_folder_path = os.path.join(base_dir, new_folder_name)
        os.makedirs(new_folder_path, exist_ok=True)
        print(f"创建新文件夹: {new_folder_path}")
        return new_folder_path

    def get_interval(self):
        """获取用户指定的下载间隔"""
        user_interval = input("请输入 float 类型下载间隔（秒，默认 3）:").strip()
        if not user_interval:
            return 3
        else:
            try:
                float_user_interval = float(user_interval)
                print("您现在输入的间隔是:", float_user_interval, "秒")
                return float_user_interval
            except ValueError:
                print("输入无效，默认使用 3 秒")
                return 3

    def update_for_uid(self, uid):
        """更新当前处理的 UID 相关属性"""
        self.uid = uid
        self.download_dir = self.get_download_dir(self.base_dir, uid)
        self.username = self.get_username(uid)
        self.saved_url_filename = os.path.join(self.download_dir, "saved_urls.log")
        self.unsaved_url_filename = os.path.join(self.download_dir, "unsaved_urls.log")
        self.date_log_filename = os.path.join(self.download_dir, "date.log")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

class URLManager:
    """管理已成功保存的 URL, 防止重复下载"""
    def __init__(self):
        self.visited = set()

    def add_url(self, url):
        if url in self.visited:
            return False
        self.visited.add(url)
        return True

    def has_url(self, url):
        return url in self.visited

    def get_all_urls(self):
        return list(self.visited)

class FileManager:
    """管理 URL 文件和 date.log 文件的加载、追加及更新"""
    def __init__(self, save_dir):
        self.save_dir = save_dir

    @staticmethod
    def load_urls(file_path):
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def append_url(file_path, url):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(url + "\n")

    @staticmethod
    def append_date(file_path, date_str):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(date_str + "\n")

    @staticmethod
    def update_unsaved_file(file_path, unsaved_set):
        with open(file_path, "w", encoding="utf-8") as f:
            for url in unsaved_set:
                f.write(url + "\n")

    def read_date_log_first_line(self):
        date_log_path = os.path.join(self.save_dir, 'date.log')
        if os.path.exists(date_log_path):
            with open(date_log_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line:
                    return first_line
        return None

    def sort_date_log(self):#排序
        date_log_path = os.path.join(self.save_dir, 'date.log')
        if os.path.exists(date_log_path):
            with open(date_log_path, 'r', encoding='utf-8') as f:
                dates = [line.strip() for line in f if line.strip()]
            if dates:
                dates.sort(reverse=True)  # 大的在上（时间晚的在上）
                with open(date_log_path, 'w', encoding='utf-8') as f:
                    for date in dates:
                        f.write(date + "\n")

class WeiboUtils:
    """工具方法集合"""
    @staticmethod
    def clean_content(content):
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'[\n\r]', ' ', content)
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_\s-]', '', content)
        cleaned = re.sub(r'\s+', ' ', cleaned).rstrip()
        return cleaned[:20].rstrip()

    @staticmethod
    def get_valid_filename(name):
        name = re.sub(r'[\\/*?:"<>|\n\r]', '', name)
        return name.rstrip()

    @staticmethod
    def safe_mkdir(path):
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError:
            base, name = os.path.split(path)
            truncated = name[:50 - len(base) - 1]
            return WeiboUtils.safe_mkdir(os.path.join(base, truncated))

    @staticmethod
    def download_media(url, path):
        if os.path.exists(path):
            return True
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
                'Referer': 'https://weibo.com/'
            }
            response = SESSION.get(url, headers=headers, stream=True, timeout=20)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        except Exception as e:
            logging.error(f"下载失败 {url}:{str(e)}")
        return False

class WeiboClient:
    """封装微博相关的接口调用与数据解析"""
    def __init__(self, uid):
        self.uid = uid

    def get_containerid(self):
        profile_url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={self.uid}"
        try:
            response = SESSION.get(profile_url, timeout=10)
            data = response.json()
            for tab in data.get('data', {}).get('tabsInfo', {}).get('tabs', []):
                if tab.get('tab_type') == 'weibo':
                    return tab.get('containerid')
        except Exception as e:
            logging.error(f"获取 containerid 失败:{str(e)}")
        return None

    def get_user_screen_name(self):
        profile_url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={self.uid}"
        try:
            response = SESSION.get(profile_url, timeout=10)
            data = response.json()
            return data.get('data', {}).get('userInfo', {}).get('screen_name', '')
        except Exception as e:
            logging.error(f"获取用户昵称失败:{str(e)}")
        return ''

    def fetch_list(self, containerid, page=1):
        api_url = f"https://m.weibo.cn/api/container/getIndex?containerid={containerid}&page={page}"
        try:
            response = SESSION.get(api_url, timeout=15)
            data = response.json()
            return data.get('data', {}).get('cards', [])
        except Exception as e:
            logging.error(f"获取微博列表失败:{str(e)}")
        return []

    def parse_weibo(self, card):
        if not card.get('mblog'):
            return None
        mblog = card['mblog']
        created_at = mblog.get('created_at', '')
        try:
            dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
            time_str = dt.strftime("%Y-%m-%d-%H-%M-%S")
            publish_time = dt.strftime("%Y%m%d%H%M%S")  # 修改为 %Y%m%d%H%M%S 格式
        except:
            time_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            publish_time = datetime.now().strftime("%Y%m%d%H%M%S")
        content = WeiboUtils.clean_content(mblog.get('text', ''))
        pics = []
        if 'pics' in mblog:
            for pic in mblog['pics']:
                if 'live_photo' in pic:
                    pics.append({'type': 'live', 'jpg_url': pic['large']['url'], 'mov_url': pic['live_photo']})
                elif 'large' in pic:
                    pics.append({'type': 'image', 'jpg_url': pic['large']['url']})
        retweeted_status = mblog.get('retweeted_status')
        if retweeted_status and 'pics' in retweeted_status:
            for pic in retweeted_status['pics']:
                if 'live_photo' in pic:
                    pics.append({'type': 'live', 'jpg_url': pic['large']['url'], 'mov_url': pic['live_photo']})
                elif 'large' in pic:
                    pics.append({'type': 'image', 'jpg_url': pic['large']['url']})
        video_url = None
        if 'page_info' in mblog and 'media_info' in mblog['page_info']:
            video_info = mblog['page_info']['media_info']
            video_url = video_info.get('stream_url_hd') or video_info.get('stream_url')
        return {
            'time': time_str,
            'content': content,
            'pics': pics,
            'video': video_url,
            'url': f"https://weibo.com/{mblog.get('user', {}).get('id')}/{mblog.get('bid')}",
            'publish_time': publish_time
        }

    def get_weibo_by_bid(self, bid):
        url = f"https://m.weibo.cn/statuses/show?id={bid}"
        try:
            response = SESSION.get(url, timeout=10)
            logging.info(f"请求 URL: {url}")
            logging.info(f"响应状态码: {response.status_code}")
            logging.info(f"响应内容前200字符: {response.text[:200]}")
            if not response.text.strip():
                logging.error("响应内容为空")
                return None
            data = response.json()
            mblog = data.get('data')
            if mblog:
                return self.parse_weibo({'mblog': mblog})
            else:
                logging.error("响应中未找到 'data' 字段")
                return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON 解析错误: {str(e)}，响应内容: {response.text[:500]}")
            return None
        except Exception as e:
            logging.error(f"获取单条微博失败: {str(e)}")
            return None

    def save_weibo(self, weibo, save_dir):
        plain_txt_dir = os.path.join(save_dir, "plain_txt")
        plain_videos_dir = os.path.join(save_dir, "plain_videos")
        os.makedirs(plain_txt_dir, exist_ok=True)
        os.makedirs(plain_videos_dir, exist_ok=True)

        if not weibo['pics'] and not weibo['video']:
            txt_filename = f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}.txt"
            txt_path = os.path.join(plain_txt_dir, txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"内容:{weibo['content']}\n链接:{weibo['url']}")
        elif not weibo['pics'] and weibo['video']:
            video_filename = f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}.mp4"
            video_path = os.path.join(plain_videos_dir, video_filename)
            if WeiboUtils.download_media(weibo['video'], video_path):
                txt_filename = f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}.txt"
                txt_path = os.path.join(plain_videos_dir, txt_filename)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"内容:{weibo['content']}\n链接:{weibo['url']}")
        else:
            base_dir = os.path.join(save_dir, f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}").rstrip()
            actual_path = WeiboUtils.safe_mkdir(base_dir)
            txt_path = os.path.join(actual_path, "content.txt")
            if not os.path.exists(txt_path):
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"内容:{weibo['content']}\n链接:{weibo['url']}")
            media_count = 1
            for media in weibo['pics']:
                if media['type'] == 'image':
                    media_path = os.path.join(actual_path, f"image_{media_count}.jpg")
                    if not WeiboUtils.download_media(media['jpg_url'], media_path):
                        return False
                elif media['type'] == 'live':
                    mov_path = os.path.join(actual_path, f"live_photo_{media_count}.mov")
                    if not WeiboUtils.download_media(media['mov_url'], mov_path):
                        return False
                    jpg_path = os.path.join(actual_path, f"live_photo_{media_count}.jpg")
                    if not WeiboUtils.download_media(media['jpg_url'], jpg_path):
                        return False
                media_count += 1
            if weibo['video']:
                video_path = os.path.join(actual_path, "video.mp4")
                WeiboUtils.download_media(weibo['video'], video_path)
        # 保存成功后，将发布时间追加到 date.log
        date_log_path = os.path.join(save_dir, "date.log")
        FileManager.append_date(date_log_path, weibo['publish_time'])
        return True

class DynamicProcessor:
    def __init__(self, file_manager, client, url_manager, cutoff_time, method):
        self.file_manager = file_manager
        self.client = client
        self.url_manager = url_manager
        self.cutoff_time = cutoff_time  # 截止时间从 date.log 第一行读取
        self.method = method

    def process_dynamic(self, weibo):
        publish_time = weibo['publish_time']

        if self.method == 'date':
            if self.cutoff_time and publish_time <= self.cutoff_time:
                logging.info(f"达到或早于截止时间 {self.cutoff_time}，停止处理")
                return False

        if self.method == 'url':
            if self.url_manager.has_url(weibo['url']):
                logging.info(f"这条已经保存:{weibo['url']}")
                return True
            if self.cutoff_time and publish_time <= self.cutoff_time:
                logging.info(f"发布时间 {publish_time} 早于截止时间 {self.cutoff_time}，跳过")
                return True  # 跳过但不停止爬取

        if self.client.save_weibo(weibo, self.file_manager.save_dir):
            self.url_manager.add_url(weibo['url'])
            self.file_manager.append_url(os.path.join(self.file_manager.save_dir, "saved_urls.log"), weibo['url'])
            logging.info(f"成功保存:{weibo['content']}")
            return True
        else:
            logging.error(f"保存失败:{weibo['url']}")
            return False

class WeiboCrawler:
    def __init__(self, uid, save_dir, interval, method):
        self.uid = uid
        self.save_dir = save_dir
        self.interval = interval
        self.client = WeiboClient(uid)
        self.url_manager = URLManager()
        self.file_manager = FileManager(save_dir)
        self.saved_urls_file = os.path.join(save_dir, "saved_urls.log")
        self.unsaved_urls_file = os.path.join(save_dir, "unsaved_urls.log")
        if not os.path.exists(self.unsaved_urls_file):
            open(self.unsaved_urls_file, "w", encoding="utf-8").close()
        for url in FileManager.load_urls(self.saved_urls_file):
            self.url_manager.add_url(url)
        self.unsaved_set = set(FileManager.load_urls(self.unsaved_urls_file))
        cutoff_time = self.file_manager.read_date_log_first_line()  # 读取 date.log 第一行作为截止时间
        self.processor = DynamicProcessor(self.file_manager, self.client, self.url_manager, cutoff_time, method)

    def crawl(self):
        containerid = self.client.get_containerid()
        if not containerid:
            logging.error("无法获取 containerid,请检查 Cookie 和 用户ID")
            return

        total = 0
        success = 0
        failed = 0
        page = 1
        start_time = time.time()
        stop_crawling = False  # 新增停止标志

        while not stop_crawling:  # 修改循环条件
            logging.info(f"正在获取第 {page} 页数据...")
            cards = self.client.fetch_list(containerid, page)
            if not cards:
                logging.info("没有更多数据")
                break

            for card in cards:
                if stop_crawling:  # 检查是否应该停止
                    break
                if card.get('card_type') != 9:
                    continue
                weibo = self.client.parse_weibo(card)
                if not weibo:
                    continue
                total += 1
                try:
                    process_result = self.processor.process_dynamic(weibo)
                    if process_result is False:
                        if self.processor.method == 'date':
                            logging.info(f"达到截止时间 {self.processor.cutoff_time}，停止爬取")
                            stop_crawling = True  # 设置停止标志
                            break  # 跳出当前页的卡片循环
                    if process_result:  # 处理成功时更新成功计数
                        if weibo['url'] in self.unsaved_set:
                            self.unsaved_set.remove(weibo['url'])
                            FileManager.update_unsaved_file(self.unsaved_urls_file, self.unsaved_set)
                        success += 1
                        time.sleep(self.interval)
                except Exception as e:
                    logging.error(f"保存异常:{str(e)}")
                    failed += 1
                    if weibo['url'] not in self.unsaved_set:
                        self.unsaved_set.add(weibo['url'])
                        FileManager.update_unsaved_file(self.unsaved_urls_file, self.unsaved_set)

            if stop_crawling:  # 跳出外层循环
                break
            page += 1
            time.sleep(self.interval + 2)

        # 爬取结束后对 date.log 进行排序
        self.file_manager.sort_date_log()

        elapsed = time.time() - start_time
        logging.info("\n====== 统计结果 ======")
        logging.info(f"总计处理:{total} 条")
        logging.info(f"成功保存:{success} 条")
        logging.info(f"失败数量:{failed} 条")
        logging.info(f"耗时:{elapsed:.2f} 秒")

class OperationMenu:
    def __init__(self, config):
        self.config = config

    def run(self):
        while True:
            choice = input(
                "\n请选择操作:\n"
                "1. 开始新抓取\n"
                "2. 重试失败URL\n"
                "3. 退出\n"
                "4. 修改UID\n请输入数字: "
            ).strip()
            if choice == "1":
                method_choice = input(
                    "请选择保存方法:\n"
                    "1. 使用 date.log 截止日期停止，不检查 saved_urls.log\n"
                    "2. 检查 saved_urls.log，不使用 date.log 截止日期\n"
                    "请输入数字: "
                ).strip()
                if method_choice == "1":
                    method = 'date'
                elif method_choice == "2":
                    method = 'url'
                else:
                    print("无效选择，默认使用方法1")
                    method = 'date'

                for uid in self.config.uid_list:
                    print(f"\n开始下载UID: {uid}")
                    self.config.update_for_uid(uid)
                    client = WeiboClient(uid)
                    screen_name = client.get_user_screen_name() or f"unknown_{uid}"
                    folder_name = f"{WeiboUtils.get_valid_filename(screen_name)}_{uid}"
                    user_save_dir = os.path.join(self.config.base_dir, folder_name)
                    os.makedirs(user_save_dir, exist_ok=True)
                    setup_logger(user_save_dir)
                    crawler = WeiboCrawler(uid, user_save_dir, self.config.interval, method)
                    crawler.crawl()
                    long_interval = 4.44
                    print("\n")
                    print("开始尖端科技之time.sleep", long_interval, "秒")
                    print("\n")
                    time.sleep(long_interval)
            elif choice == "2":
                for root, dirs, files in os.walk(self.config.base_dir):
                    for dir_name in dirs:
                        user_dir = os.path.join(root, dir_name)
                        unsaved_file = os.path.join(user_dir, "unsaved_urls.log")
                        if os.path.exists(unsaved_file):
                            with open(unsaved_file, "r", encoding="utf-8") as f:
                                unsaved_urls = [line.strip() for line in f if line.strip()]
                            if unsaved_urls:
                                print(f"\n重试文件夹: {dir_name} 的失败URL")
                                uid = dir_name.split('_')[-1]
                                client = WeiboClient(uid)
                                crawler = WeiboCrawler(uid, user_dir, self.config.interval, method='url')
                                for url in unsaved_urls:
                                    bid = extract_bid_from_url(url)
                                    if bid:
                                        weibo = client.get_weibo_by_bid(bid)
                                        if weibo and crawler.processor.process_dynamic(weibo):
                                            crawler.unsaved_set.remove(url)
                                            FileManager.update_unsaved_file(unsaved_file, crawler.unsaved_set)
                                            FileManager.append_url(os.path.join(user_dir, "saved_urls.log"), url)
                                            logging.info(f"成功保存:{url}")
                                        else:
                                            logging.error(f"保存失败:{url}")
                                    time.sleep(self.config.interval)
            elif choice == "3":
                print("程序退出")
                break
            elif choice == "4":
                self.change_uid()
            else:
                print("无效输入，请重新选择")

    def change_uid(self):
        new_uid_input = input("请输入新的UID（多个UID用逗号分隔）: ").strip()
        if new_uid_input:
            self.config.uid_list = [uid.strip() for uid in new_uid_input.split(',')]
            print(f"UID列表已更新为: {self.config.uid_list}")
        else:
            print("UID列表未更改")

def extract_bid_from_url(url):
    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    if len(path_parts) >= 3 and path_parts[2]:
        bid = path_parts[2]
        logging.info(f"从 URL {url} 提取到的 bid: {bid}")
        return bid
    return None

def setup_logger(save_dir):
    log_file = os.path.join(save_dir, f"weibo_crawler_{datetime.now().strftime('%Y%m%d%H%M')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return log_file

def main():
    print("这是微博爬取的程序")
    print("Kitaro绮太郎1923024604 半年可见")
    print("坂坂白 5491928243 半年可见\n")

    config = Config()
    SESSION.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'Cookie': config.COOKIE
    })

    menu = OperationMenu(config)
    menu.run()

if __name__ == "__main__":
    main()
