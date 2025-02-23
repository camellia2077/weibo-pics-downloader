import os
import re
import time
import json
import requests
from datetime import datetime
import logging
from urllib.parse import urlparse
import random

# 在此处填写你的微博 Cookie(必需)
COOKIES = ""

# 新增保存路径记录
        #logging.info(f"正在保存到文件夹: {os.path.basename(actual_path)}") 

# 基础配置
DEFAULT_UID = "2683370593"
DEFAULT_SAVE_DIR = "C:\\Base1\\bbb\\weibo"
DELAY_RANGE = (0.05, 0.1)
SESSION = requests.Session()

class Config:
    """配置管理类"""
    def __init__(self, save_dir):
        self.save_dir = save_dir
        self.saved_url_filename = os.path.join(save_dir, "saved_urls.txt")
        self.unsaved_url_filename = os.path.join(save_dir, "unsaved_urls.txt")
        self.interval = 0.5

class URLManager:
    """管理已成功保存的 URL"""
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
    """增强版文件管理"""
    @staticmethod
    def load_urls(file_path):
        """加载URL列表"""
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def load_url_set(file_path):
        """加载URL集合"""
        return set(FileManager.load_urls(file_path))

    @staticmethod
    def append_url(file_path, url):
        """追加单个URL"""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(url + "\n")

    @staticmethod
    def append_url_file(file_path, urls):
        """批量追加URL"""
        with open(file_path, "a", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")

    @staticmethod
    def write_url_file(file_path, urls):
        """覆盖写入URL列表"""
        with open(file_path, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")

class WeiboUtils:
    @staticmethod
    def clean_content(content):
        content = re.sub(r'<[^>]+>', '', content)
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_\-\\s]', '', content)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned[:20]

    @staticmethod
    def get_valid_filename(name):
        return re.sub(r'[\\/*?:"<>|]', "", name)

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
            delay = random.uniform(*DELAY_RANGE)
            time.sleep(delay)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
    def __init__(self, uid):
        self.uid = uid

    def get_containerid(self):
        profile_url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={self.uid}"
        try:
            delay = random.uniform(*DELAY_RANGE)
            time.sleep(delay)
            response = SESSION.get(profile_url, timeout=10)
            data = response.json()
            for tab in data.get('data', {}).get('tabsInfo', {}).get('tabs', []):
                if tab.get('tab_type') == 'weibo':
                    return tab.get('containerid')
        except Exception as e:
            logging.error(f"获取 containerid 失败:{str(e)}")
        return None

    def fetch_list(self, containerid, page=1, since_id=None, retry=3):
        """修改后的分页获取方法（支持since_id）"""
        params = {
            'containerid': containerid,
            'page': page
        }
        if since_id:
            params['since_id'] = since_id

        for attempt in range(retry):
            try:
                delay = random.uniform(*DELAY_RANGE)
                time.sleep(delay)
                response = SESSION.get("https://m.weibo.cn/api/container/getIndex", 
                                     params=params, timeout=15)
                data = response.json()
                cards = data.get('data', {}).get('cards', [])
                cardlist_info = data.get('data', {}).get('cardlistInfo', {})
                next_since_id = cardlist_info.get('since_id')
                return cards, next_since_id
            except Exception as e:
                if attempt < retry - 1:
                    wait = 2 ** attempt
                    logging.warning(f"请求失败，{wait}秒后重试 ({str(e)})")
                    time.sleep(wait)
                else:
                    logging.error(f"重试{retry}次后失败")
                    return [], None

    def parse_weibo(self, card):
        if not card.get('mblog'):
            return None
        mblog = card['mblog']
        created_at = mblog.get('created_at', '')
        try:
            dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
            time_str = dt.strftime("%Y-%m-%d-%H-%M-%S")
        except:
            time_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        content = WeiboUtils.clean_content(mblog.get('text', ''))
        pics = []
        
        if 'pics' in mblog:
            for pic in mblog['pics']:
                if 'large' in pic:
                    pics.append(pic['large']['url'])
        
        retweeted_status = mblog.get('retweeted_status')
        if retweeted_status:
            current_retweet = retweeted_status
            while True:
                if 'pics' in current_retweet:
                    for pic in current_retweet['pics']:
                        if 'large' in pic:
                            pics.append(pic['large']['url'])
                if 'retweeted_status' in current_retweet and current_retweet['retweeted_status']:
                    current_retweet = current_retweet['retweeted_status']
                else:
                    break

        video_url = None
        if 'page_info' in mblog and 'media_info' in mblog['page_info']:
            video_info = mblog['page_info']['media_info']
            video_url = video_info.get('stream_url_hd') or video_info.get('stream_url')
        return {
            'time': time_str,
            'content': content,
            'pics': pics,
            'video': video_url,
            'url': f"https://weibo.com/{mblog.get('user', {}).get('id')}/{mblog.get('bid')}"
        }

class WeiboProcessor:
    """微博动态处理器"""
    def __init__(self, client, config, file_manager):
        self.client = client
        self.config = config
        self.file_manager = file_manager

    def process_weibo(self, weibo, url_manager, success_list, failed_list):
        """处理单条微博"""
        url = weibo['url']
        if url_manager.has_url(url):
            return True
        
        try:
            if self.save_weibo(weibo):
                success_list.append(url)
                url_manager.add_url(url)
                self.file_manager.append_url(self.config.saved_url_filename, url)
                return True
            else:
                failed_list.append(url)
                return False
        except Exception as e:
            logging.error(f"处理异常:{str(e)}")
            failed_list.append(url)
            return False

    def save_weibo(self, weibo):
        """保存微博内容"""
        base_dir = os.path.join(self.config.save_dir, f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}")
        actual_path = WeiboUtils.safe_mkdir(base_dir)
        
        # 新增保存路径记录
        logging.info(f"正在保存到文件夹: {os.path.basename(actual_path)}")  # 只显示文件夹名称
        # 如果要显示完整路径可以使用：
        # logging.info(f"保存路径: {actual_path}")

        txt_path = os.path.join(actual_path, "content.txt")
        
        if not os.path.exists(txt_path):
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"内容:{weibo['content']}\n链接:{weibo['url']}")
        
        img_count = 1
        for img_url in weibo['pics']:
            ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
            img_path = os.path.join(actual_path, f"{img_count}{ext}")
            if not WeiboUtils.download_media(img_url, img_path):
                return False
            img_count += 1
        
        if weibo['video']:
            video_path = os.path.join(actual_path, "video.mp4")
            WeiboUtils.download_media(weibo['video'], video_path)
        
        # 新增成功提示
        logging.info(f"成功保存到: {os.path.basename(actual_path)}")
        return True

class RetryFailedUrls:
    """重试失败URL"""
    def __init__(self, config, file_manager, processor):
        self.config = config
        self.file_manager = file_manager
        self.processor = processor
        self.saved_urls = self.file_manager.load_url_set(config.saved_url_filename)
        self.success_list = []
        self.failed_list = []

    def _get_weibo_detail(self, weibo_id):
        """获取微博详情"""
        api_url = f"https://m.weibo.cn/statuses/show?id={weibo_id}"
        try:
            response = SESSION.get(api_url, timeout=10)
            if response.status_code != 200:
                logging.error(f"请求失败 状态码:{response.status_code}")
                return None
            data = response.json()
            return data.get('data')
        except Exception as e:
            logging.error(f"获取微博详情失败: {e}")
            return None

    def _process_single_url(self, url):
        """处理单个URL"""
        logging.info(f"\n{'='*30}\n正在处理URL: {url}")
        
        if not url.startswith("https://weibo.com/"):
            logging.error("非标准微博URL，跳过")
            return False
            
        weibo_id = url.split("/")[-1]
        data = self._get_weibo_detail(weibo_id)
        if not data:
            logging.error("获取微博数据失败")
            return False

        weibo = {
            'time': datetime.fromtimestamp(data['created_timestamp']).strftime("%Y-%m-%d-%H-%M-%S"),
            'content': WeiboUtils.clean_content(data['text']),
            'pics': [pic['large']['url'] for pic in data.get('pics', [])],
            'video': data.get('page_info', {}).get('media_info', {}).get('stream_url'),
            'url': url
        }

        return self.processor.process_weibo(
            weibo,
            URLManager(),  # 临时管理器，避免重复处理
            self.success_list,
            self.failed_list
        )

    def run(self):
        """执行重试操作"""
        logging.info("\n开始重试未成功下载的URL...")
        unsaved_urls = self.file_manager.load_url_set(self.config.unsaved_url_filename)
        if not unsaved_urls:
            logging.info("没有需要重试的URL")
            return

        retry_queue = list(unsaved_urls)
        total_count = len(retry_queue)
        success_count = 0
        retry_limit = 2

        for attempt in range(retry_limit):
            logging.info(f"\n第{attempt+1}次重试 (剩余{len(retry_queue)}条)")
            temp_failed = []
            
            for url in retry_queue:
                time.sleep(random.uniform(1.0, 2.0))
                if self._process_single_url(url):
                    success_count += 1
                    unsaved_urls.discard(url)
                else:
                    temp_failed.append(url)
                    
            retry_queue = temp_failed
            if not retry_queue:
                break

        if self.success_list:
            self.file_manager.append_url_file(self.config.saved_url_filename, self.success_list)
        self.file_manager.write_url_file(self.config.unsaved_url_filename, list(unsaved_urls))
        
        logging.info(f"\n{'='*30}")
        logging.info(f"重试完成! 成功{success_count}/{total_count}条")
        if retry_queue:
            logging.info(f"以下URL仍然失败:\n" + "\n".join(retry_queue))

class OperationMenu:
    """操作菜单"""
    def __init__(self, config, file_manager, client):
        self.config = config
        self.file_manager = file_manager
        self.client = client
        self.processor = WeiboProcessor(client, config, file_manager)

    def run(self):
        while True:
            choice = input(
                "\n请选择操作:\n"
                "1. 开始新抓取\n"
                "2. 重试失败URL\n"
                "3. 退出\n请输入数字: "
            ).strip()

            if choice == "1":
                self._start_new_crawl()
            elif choice == "2":
                RetryFailedUrls(self.config, self.file_manager, self.processor).run()
            elif choice == "3":
                print("程序退出")
                break
            else:
                print("无效输入，请重新选择")

    def _start_new_crawl(self):
        """修改后的抓取主逻辑（支持分页标记）"""
        url_manager = URLManager()
        for url in self.file_manager.load_urls(self.config.saved_url_filename):
            url_manager.add_url(url)

        containerid = self.client.get_containerid()
        if not containerid:
            logging.error("无法获取 containerid，请检查 Cookie 和 用户ID")
            return

        page = 1
        since_id = None
        max_empty_pages = 3  # 连续空页数阈值
        empty_count = 0

        while True:
            logging.info(f"正在获取数据 [页码:{page}, since_id:{since_id}]...")
            cards, next_since_id = self.client.fetch_list(containerid, page, since_id)
            
            if not cards:
                empty_count += 1
                logging.warning(f"第{empty_count}次获取到空数据")
                if empty_count >= max_empty_pages:
                    logging.info("连续获取到空数据，终止抓取")
                    break
                if next_since_id:
                    logging.info("检测到分页标记，重置页码")
                    since_id = next_since_id
                    page = 1
                    empty_count = 0
                    continue
                else:
                    break

            empty_count = 0  # 重置空页计数器
            success_list = []
            failed_list = []
            
            for card in cards:
                if card.get('card_type') != 9:
                    continue
                weibo = self.client.parse_weibo(card)
                if not weibo:
                    continue

                self.processor.process_weibo(
                    weibo,
                    url_manager,
                    success_list,
                    failed_list
                )

            if failed_list:
                self.file_manager.append_url_file(
                    self.config.unsaved_url_filename,
                    failed_list
                )

            # 处理分页标记
            if next_since_id:
                since_id = next_since_id
                page = 1  # 使用since_id时重置页码
                logging.info(f"获取到新分页标记: {since_id}")
            else:
                page += 1  # 传统页码递增

            logging.info(f"本页处理完成: 成功{len(success_list)}条，失败{len(failed_list)}条")
            time.sleep(self.config.interval + random.uniform(0, 2))

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
    print("赵喵喵5839848157 半年可见")
    print("Kitaro绮太郎1923024604 半年可见")
    print("坂坂白 5491928243 半年可见\n")
    uid = input(f"请输入用户ID(默认{DEFAULT_UID}): ") or DEFAULT_UID
    save_dir = input(f"请输入保存目录(默认{DEFAULT_SAVE_DIR}): ") or DEFAULT_SAVE_DIR
    interval = float(input("请输入请求间隔(秒,默认5): ") or 5)
    os.makedirs(save_dir, exist_ok=True)
    setup_logger(save_dir)

    SESSION.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Cookie': COOKIES
    })

    config = Config(save_dir)
    config.interval = interval
    file_manager = FileManager()
    client = WeiboClient(uid)
    menu = OperationMenu(config, file_manager, client)
    menu.run()

if __name__ == "__main__":
    main()
