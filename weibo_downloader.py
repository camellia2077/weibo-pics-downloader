#转发中的图片也保存
import os
import re
import time
import json
import requests
from datetime import datetime
import logging
from urllib.parse import urlparse

# 在此处填写你的微博 Cookie(必需)
COOKIES = "SCF="

# 基础配置
DEFAULT_UID = "谢安然 2683370593"
DEFAULT_SAVE_DIR = "C:\\Base1\\bbb\\weibo"
SESSION = requests.Session()




class URLManager:
    """管理已成功保存的 URL,防止重复下载"""
    def __init__(self):
        self.visited = set()

    def add_url(self, url):
        """
        添加一个 URL 到 visited 集合中
        :param url: 目标 URL
        :return: 如果 URL 已存在返回 False,否则添加后返回 True
        """
        if url in self.visited:
            return False
        self.visited.add(url)
        return True

    def has_url(self, url):
        """检查 URL 是否已存在(即已经成功保存过)"""
        return url in self.visited

    def get_all_urls(self):
        """获取所有已保存的 URL 列表"""
        return list(self.visited)


class FileManager:
    """管理 URL 文件的加载、追加及更新"""
    @staticmethod
    def load_urls(file_path):
        """加载文件中的 URL 列表(如果文件存在)"""
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def append_url(file_path, url):
        """将新的 URL 追加到指定文件中"""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(url + "\n")

    @staticmethod
    def update_unsaved_file(file_path, unsaved_set):
        """更新 unsaved_urls 文件,将 unsaved_set 中的 URL 全部写入文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            for url in unsaved_set:
                f.write(url + "\n")


class WeiboUtils:
    """工具方法集合"""
    @staticmethod
    def clean_content(content):
        """清理微博内容中的非法字符"""
        content = re.sub(r'<[^>]+>', '', content)  # 移除 HTML 标签
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_\-\\s]', '', content)  # 保留中文、字母、数字、下划线、横杠及空格
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # 去除连续空白
        return cleaned[:20]  # 限制最大长度

    @staticmethod
    def get_valid_filename(name):
        """生成有效的目录名"""
        return re.sub(r'[\\/*?:"<>|]', "", name)

    @staticmethod
    def safe_mkdir(path):
        """安全创建目录,并返回实际创建的路径"""
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError:
            base, name = os.path.split(path)
            truncated = name[:50 - len(base) - 1]
            return WeiboUtils.safe_mkdir(os.path.join(base, truncated))

    @staticmethod
    def download_media(url, path):
        """下载媒体文件并返回是否成功"""
        if os.path.exists(path):
            return True
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/91.0.4472.124 Safari/537.36',
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
        """获取用户微博 """
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

    def fetch_list(self, containerid, page=1):
        """获取微博列表"""
        api_url = f"https://m.weibo.cn/api/container/getIndex?containerid={containerid}&page={page}"
        try:
            response = SESSION.get(api_url, timeout=15)
            data = response.json()
            return data.get('data', {}).get('cards', [])
        except Exception as e:
            logging.error(f"获取微博列表失败:{str(e)}")
        return []

    def parse_weibo(self, card):
        """解析单条微博数据"""
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
        # 解析当前微博图片
        if 'pics' in mblog:
            for pic in mblog['pics']:
                if 'large' in pic:
                    pics.append(pic['large']['url'])
        # 解析转发微博图片
        retweeted_status = mblog.get('retweeted_status')
        if retweeted_status and 'pics' in retweeted_status:
            for pic in retweeted_status['pics']:
                if 'large' in pic:
                    pics.append(pic['large']['url'])
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

    def save_weibo(self, weibo, save_dir):
        """保存单条微博内容"""
        base_dir = os.path.join(save_dir, f"{weibo['time']}-{WeiboUtils.get_valid_filename(weibo['content'])}")
        actual_path = WeiboUtils.safe_mkdir(base_dir)
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
        return True


class WeiboCrawler:
    """整体爬虫逻辑,负责加载历史记录、抓取、保存微博及更新记录"""
    def __init__(self, uid, save_dir, interval):
        self.uid = uid
        self.save_dir = save_dir
        self.interval = interval
        self.client = WeiboClient(uid)
        self.url_manager = URLManager()
        self.saved_urls_file = os.path.join(save_dir, "saved_urls.txt")
        self.unsaved_urls_file = os.path.join(save_dir, "unsaved_urls.txt")
        # 确保 unsaved_urls.txt 文件存在(即使为空)
        if not os.path.exists(self.unsaved_urls_file):
            open(self.unsaved_urls_file, "w", encoding="utf-8").close()
        # 加载已保存的 URL 到 URLManager 中
        for url in FileManager.load_urls(self.saved_urls_file):
            self.url_manager.add_url(url)
        # 加载保存失败的 URL 到一个集合 unsaved_set
        self.unsaved_set = set(FileManager.load_urls(self.unsaved_urls_file))

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

        while True:
            logging.info(f"正在获取第 {page} 页数据...")
            cards = self.client.fetch_list(containerid, page)
            if not cards:
                logging.info("没有更多数据")
                break

            for card in cards:
                if card.get('card_type') != 9:  # 仅处理原创微博
                    continue
                weibo = self.client.parse_weibo(card)
                if not weibo:
                    continue
                url = weibo['url']
                # 如果 URL 已在已保存列表中,则跳过
                if self.url_manager.has_url(url):
                    logging.info(f"这条已经保存:{url}")
                    continue

                total += 1
                try:
                    if self.client.save_weibo(weibo, self.save_dir):
                        success += 1
                        logging.info(f"成功保存:{weibo['content']}")
                        # 保存成功后:添加到 URLManager 和 saved_urls.txt
                        self.url_manager.add_url(url)
                        FileManager.append_url(self.saved_urls_file, url)
                        # 如果该 URL 曾在保存失败集合中,则删除
                        if url in self.unsaved_set:
                            self.unsaved_set.remove(url)
                            FileManager.update_unsaved_file(self.unsaved_urls_file, self.unsaved_set)
                    else:
                        failed += 1
                        logging.error(f"保存失败:{url}")
                        # 保存失败:加入 unsaved_set 并更新 unsaved_urls.txt
                        if url not in self.unsaved_set:
                            self.unsaved_set.add(url)
                            FileManager.update_unsaved_file(self.unsaved_urls_file, self.unsaved_set)
                    time.sleep(self.interval)
                except Exception as e:
                    logging.error(f"保存异常:{str(e)}")
                    failed += 1

            page += 1
            time.sleep(self.interval + 2)  # 增加页面切换间隔

        elapsed = time.time() - start_time
        logging.info("\n====== 统计结果 ======")
        logging.info(f"总计处理:{total} 条")
        logging.info(f"成功保存:{success} 条")
        logging.info(f"失败数量:{failed} 条")
        logging.info(f"耗时:{elapsed:.2f} 秒")


def setup_logger(save_dir):
    """配置日志记录器"""
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
    interval = int(input("请输入请求间隔(秒,默认5): ") or 5)
    os.makedirs(save_dir, exist_ok=True)
    log_file = setup_logger(save_dir)

    # 初始化 SESSION(使用代码中设置的 COOKIES)
    SESSION.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36',
        'Cookie': COOKIES
    })

    crawler = WeiboCrawler(uid, save_dir, interval)
    crawler.crawl()


if __name__ == "__main__":
    main()
